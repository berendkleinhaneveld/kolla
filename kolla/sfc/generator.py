import ast

from .analyser import Expression, ScopeFinder
from .parser import DIRECTIVE_BIND, DIRECTIVE_ON, Element, Text, is_directive


def generate(tree, analysis, class_name):
    # Process tree
    fragment_function = ast_create_fragment_function(tree, analysis)

    # Create component class
    class_tree = ast_create_component_class(class_name)

    # Create instance function from the script tag
    script = analysis["script"]
    if not script:
        instance_function = ast.FunctionDef(
            name="instance",
            args=ast.arguments(
                posonlyargs=[],
                args=[
                    ast.arg(arg="__self"),
                    ast.arg(arg="__props"),
                    ast.arg(arg="__invalidate"),
                ],
                kwonlyargs=[],
                kw_defaults=[],
                defaults=[],
            ),
            body=[
                ast.Return(value=ast.Dict(keys=[], values=[])),
            ],
            decorator_list=[],
        )
    else:
        instance_function = ast_instance_function(script.content, analysis)

    import_collector = ImportCollector(imports=analysis["scope"].imports)
    import_collector.visit(instance_function)

    module = ast.Module(
        body=[
            # Import some runtime dependencies
            ast.ImportFrom(
                module="kolla.runtime",
                names=[
                    ast.alias(name="Component"),
                    ast.alias(name="create_component"),
                    ast.alias(name="destroy_component"),
                    ast.alias(name="mount_component"),
                    ast.alias(name="Fragment"),
                ],
                level=0,
            ),
            # Import all imports from the script
            *analysis["scope"].imports,
            fragment_function,
            instance_function,
            class_tree,
        ],
        type_ignores=[],
    )
    return module


class ImportCollector(ast.NodeTransformer):
    def __init__(self, imports):
        super().__init__()
        self.imports = imports

    def generic_visit(self, node):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if node in self.imports:
                return None
        return super().generic_visit(node)


def ast_create_fragment_function(tree, analysis):
    items = []

    def gather_elements(element):
        if isinstance(element, (Element, Text)):
            items.append(element)

        if hasattr(element, "children"):
            for child in element.children:
                gather_elements(child)

    gather_elements(tree)

    components = [item for item in items if item.is_component]
    elements = [item for item in items if not item.is_component]

    element_declarations = [
        ast.Assign(
            targets=[ast.Name(id=item.name, ctx=ast.Store())],
            value=ast.Constant(value=None),
        )
        for item in elements
    ]

    def props_for_component(component):
        keys = []
        values = []

        for attr in component.attributes:
            if isinstance(attr.value, Expression):
                val = unfold_dynamic_attribute_value(attr.value, analysis["variables"])
            else:
                val = ast.Constant(value=attr.value)
            keys.append(ast.Constant(value=attr.key))
            values.append(val)

        return ast.Dict(keys=keys, values=values)

    component_declarations = [
        ast.Assign(
            targets=[ast.Name(id=item.name, ctx=ast.Store())],
            value=ast.Call(
                func=ast.Name(id=item.tag, ctx=ast.Load()),
                args=[
                    ast.Dict(
                        keys=[ast.Constant(value="renderer")],
                        values=[ast.Name(id="renderer", ctx=ast.Load())],
                    )
                ],
                keywords=[
                    ast.keyword(
                        arg="props",
                        value=props_for_component(item),
                    )
                ],
            ),
        )
        for item in components
    ]

    def create_call_for_element(element):
        if isinstance(element, Text):
            return ast.Call(
                func=ast.Attribute(
                    value=ast.Name(id="renderer", ctx=ast.Load()),
                    attr="create_text_element",
                    ctx=ast.Load(),
                ),
                args=[],
                keywords=[],
            )
        return ast.Call(
            func=ast.Attribute(
                value=ast.Name(id="renderer", ctx=ast.Load()),
                attr="create_element",
                ctx=ast.Load(),
            ),
            args=[ast.Constant(value=element.tag)],
            keywords=[],
        )

    element_creations = [
        ast.Assign(
            targets=[ast.Name(id=item.name, ctx=ast.Store())],
            value=create_call_for_element(item),
        )
        for item in elements
    ]

    def create_call_for_component(component):
        # TODO: the right arguments
        return ast.Expr(
            value=ast.Call(
                func=ast.Name(id="create_component", ctx=ast.Load()),
                args=[
                    ast.Attribute(
                        value=ast.Name(id=component.name, ctx=ast.Load()),
                        attr="fragment",
                        ctx=ast.Load(),
                    )
                ],
                keywords=[],
            )
        )

    component_creations = [create_call_for_component(item) for item in components]

    element_set_attributes = []
    remove_event_listeners = []
    for element in items:
        if element.is_component:
            continue
        set_attributes, event_listeners = ast_set_attributes(element, analysis)
        element_set_attributes.extend(set_attributes)
        remove_event_listeners.extend(
            [
                ast_remove_event_listener(*event_listener, analysis)
                for event_listener in event_listeners
            ]
        )

    def mount_expression(item):
        if item.is_component:
            return ast.Expr(
                value=ast.Call(
                    func=ast.Name(id="mount_component", ctx=ast.Load()),
                    args=[
                        ast.Name(id=item.name, ctx=ast.Load()),
                        ast.Name(
                            id="parent" if item.parent is None else item.parent.name,
                            ctx=ast.Load(),
                        ),
                        ast.Name(id="anchor", ctx=ast.Load()),
                    ],
                    keywords=[],
                ),
            )
        else:
            return ast.Expr(
                value=ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(id="renderer", ctx=ast.Load()),
                        attr="insert",
                        ctx=ast.Load(),
                    ),
                    args=[
                        ast.Name(id=item.name, ctx=ast.Load()),
                        ast.Name(
                            id="parent" if item.parent is None else item.parent.name,
                            ctx=ast.Load(),
                        ),
                        ast.Name(id="anchor", ctx=ast.Load()),
                    ],
                    keywords=[],
                ),
            )

    # Mounts need to be processed in the order that they appear in the template
    mounts = [mount_expression(item) for item in items]

    element_updates = []
    component_updates = []
    for item in components:
        component_updates.append(
            ast.Assign(
                targets=[ast.Name(id=f"{item.name}_changes", ctx=ast.Store())],
                value=ast.Dict(keys=[], values=[]),
            )
        )

    for name in analysis["will_change_elements"]:
        for element, attr in analysis["will_change_elements"][name]:
            if not attr.name.startswith((DIRECTIVE_BIND, ":")):
                continue
            if not element.is_component:
                element_updates.append(
                    ast.If(
                        test=ast.Compare(
                            left=ast.Constant(value=name),
                            ops=[ast.In()],
                            comparators=[
                                ast.Name(
                                    id="dirty",
                                    ctx=ast.Load(),
                                )
                            ],
                        ),
                        body=[
                            ast_set_dynamic_attribute(
                                element,
                                attr.name,
                                attr.value,
                                analysis["variables"],
                            )
                        ],
                        orelse=[],
                    )
                )
            else:
                if attr.name.startswith((":", DIRECTIVE_BIND)):
                    _, key = attr.name.split(":")
                else:
                    key = attr.name
                if isinstance(attr.value, Expression):
                    val = unfold_dynamic_attribute_value(
                        attr.value, analysis["variables"]
                    )
                else:
                    val = ast.Constant(value=attr.value)
                component_updates.append(
                    ast.If(
                        test=ast.Compare(
                            left=ast.Constant(value=name),
                            ops=[ast.In()],
                            comparators=[
                                ast.Name(
                                    id="dirty",
                                    ctx=ast.Load(),
                                )
                            ],
                        ),
                        body=[
                            ast.Assign(
                                targets=[
                                    ast.Subscript(
                                        value=ast.Name(
                                            id=f"{element.name}_changes",
                                            ctx=ast.Load(),
                                        ),
                                        slice=ast.Constant(value=key),
                                        ctx=ast.Store(),
                                    )
                                ],
                                value=val,
                            ),
                        ],
                        orelse=[],
                    )
                )

    for item in components:
        component_updates.append(
            ast.Expr(
                value=ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(id=item.name, ctx=ast.Load()),
                        attr="set",
                        ctx=ast.Load(),
                    ),
                    args=[ast.Name(id=f"{item.name}_changes", ctx=ast.Load())],
                    keywords=[],
                )
            )
        )

    if not element_updates and not component_updates:
        element_updates.append(ast.Pass())

    nonlocal_statement = [ast.Nonlocal(names=list([item.name for item in elements]))]
    if not nonlocal_statement[0].names:
        nonlocal_statement = [ast.Pass()]

    return ast.FunctionDef(
        name="create_fragment",
        args=ast.arguments(
            posonlyargs=[],
            args=[
                ast.arg(
                    arg="context",
                    annotation=ast.Name(
                        id="dict",
                        ctx=ast.Load(),
                    ),
                ),
                ast.arg(arg="renderer"),
            ],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[],
        ),
        body=[
            # Declare the element variables
            *element_declarations,
            *component_declarations,
            ast.Assign(
                targets=[ast.Name(id="__parent", ctx=ast.Store())],
                value=ast.Constant(value=None),
            ),
            ast.FunctionDef(
                name="create",
                args=ast.arguments(
                    posonlyargs=[],
                    args=[],
                    kwonlyargs=[],
                    kw_defaults=[],
                    defaults=[],
                ),
                body=[
                    *nonlocal_statement,
                    *element_creations,
                    *element_set_attributes,
                    *component_creations,
                ],
                decorator_list=[],
            ),
            ast.FunctionDef(
                name="mount",
                args=ast.arguments(
                    posonlyargs=[],
                    args=[ast.arg(arg="parent"), ast.arg(arg="anchor")],
                    kwonlyargs=[],
                    kw_defaults=[],
                    defaults=[ast.Constant(value=None)],
                ),
                body=[
                    ast.Nonlocal(names=["__parent"]),
                    ast.Assign(
                        targets=[ast.Name(id="__parent", ctx=ast.Store())],
                        value=ast.Name(id="parent", ctx=ast.Load()),
                    ),
                    *mounts,
                ],
                decorator_list=[],
            ),
            ast.FunctionDef(
                name="update",
                args=ast.arguments(
                    posonlyargs=[],
                    args=[ast.arg(arg="context"), ast.arg(arg="dirty")],
                    kwonlyargs=[],
                    kw_defaults=[],
                    defaults=[],
                ),
                body=[*element_updates, *component_updates],
                decorator_list=[],
            ),
            ast.FunctionDef(
                name="destroy",
                args=ast.arguments(
                    posonlyargs=[],
                    args=[],
                    kwonlyargs=[],
                    kw_defaults=[],
                    defaults=[],
                ),
                body=[
                    # FIXME: Call destroy_component for components
                    ast.Expr(
                        value=ast.Call(
                            func=ast.Attribute(
                                value=ast.Name(id="renderer", ctx=ast.Load()),
                                attr="remove",
                                ctx=ast.Load(),
                            ),
                            args=[
                                ast.Name(id="__element", ctx=ast.Load()),
                                ast.Name(id="__parent", ctx=ast.Load()),
                            ],
                            keywords=[],
                        ),
                    ),
                    *remove_event_listeners,
                ],
                decorator_list=[],
            ),
            ast.Return(
                value=ast.Call(
                    func=ast.Name(id="Fragment", ctx=ast.Load()),
                    args=[
                        ast.Name(id="create", ctx=ast.Load()),
                        ast.Name(id="mount", ctx=ast.Load()),
                        ast.Name(id="update", ctx=ast.Load()),
                        ast.Name(id="destroy", ctx=ast.Load()),
                    ],
                    keywords=[],
                )
            ),
        ],
        decorator_list=[],
        returns=ast.Name(id="Fragment", ctx=ast.Load()),
    )


def ast_create_component_class(class_name):
    return ast.ClassDef(
        name=class_name,
        bases=[ast.Name(id="Component", ctx=ast.Load())],
        keywords=[],
        body=[
            ast.FunctionDef(
                name="__init__",
                args=ast.arguments(
                    posonlyargs=[],
                    args=[
                        ast.arg(arg="self"),
                        ast.arg(arg="options"),
                        ast.arg(arg="props"),
                    ],
                    kwonlyargs=[],
                    kw_defaults=[],
                    defaults=[
                        ast.Constant(value=None),
                        ast.Constant(value=None),
                    ],
                ),
                body=[
                    ast.Expr(
                        value=ast.Call(
                            func=ast.Attribute(
                                value=ast.Call(
                                    func=ast.Name(id="super", ctx=ast.Load()),
                                    args=[],
                                    keywords=[],
                                ),
                                attr="__init__",
                                ctx=ast.Load(),
                            ),
                            args=[
                                ast.Name(id="options", ctx=ast.Load()),
                                ast.Name(id="instance", ctx=ast.Load()),
                                ast.Name(id="create_fragment", ctx=ast.Load()),
                            ],
                            keywords=[
                                ast.keyword(
                                    "props", ast.Name(id="props", ctx=ast.Load())
                                )
                            ],
                        )
                    )
                ],
                decorator_list=[],
            )
        ],
        decorator_list=[],
    )


def ast_instance_function(script_tree, analysis):
    wrapped_nodes = set()
    for key, nodes in analysis["will_change"].items():
        wrapped_nodes.update(nodes)

    invalidator_wrapper = NodeInvalidatorWrapper(wrapped_nodes)
    invalidator_wrapper.visit(script_tree)

    symbols = [
        ast.Constant(value=symbol) for symbol in analysis["will_use_in_template"]
    ]

    symbol_refs = [ast.Name(id=name.value, ctx=ast.Load()) for name in symbols]

    scope_finder = ScopeFinder()
    scope_finder.visit(script_tree)

    # A component script is written at module level, but instead it will
    # be instantiated and run within a function scope. Hence, the global
    # scope will have to be updated to nonlocal instead.
    # FIXME: This could potentially lead to name clashes with actual nonlocal statements
    # I guess this should be mentioned in the docs somewhere
    GlobalToNonLocal().visit(script_tree)

    for symbol in analysis["will_use_in_template"]:

        class AssignmentsFinder(ast.NodeTransformer):
            def __init__(self):
                super().__init__()
                self.nodes = []

            def generic_visit(self, node):
                # Wrap each assign in the global root scope
                if (
                    isinstance(node, ast.Assign)
                    and node.targets[0] in scope_finder.globals
                ):
                    return ast.Assign(
                        targets=node.targets,
                        value=ast.Call(
                            func=ast.Attribute(
                                value=ast.Name(id="__props", ctx=ast.Load()),
                                attr="get",
                                ctx=ast.Load(),
                            ),
                            args=[
                                ast.Constant(value=node.targets[0].id),
                                node.value,
                            ],
                            keywords=[],
                        ),
                    )
                return super().generic_visit(node)

        AssignmentsFinder().visit(script_tree)

    return ast.FunctionDef(
        name="instance",
        args=ast.arguments(
            posonlyargs=[],
            args=[
                ast.arg(arg="__self"),
                ast.arg(arg="__props"),
                ast.arg(arg="__invalidate"),
            ],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[],
        ),
        body=[
            *script_tree.body,
            ast.Return(
                value=ast.Dict(
                    keys=[*symbols],
                    values=[*symbol_refs],
                )
            ),
        ],
        decorator_list=[],
    )


def ast_set_attributes(element: Element, analysis):
    assert isinstance(element, (Element, Text)), element
    result = []
    event_listeners = []

    if isinstance(element, Text):
        result.append(
            ast.Expr(
                value=ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(id="renderer", ctx=ast.Load()),
                        attr="set_element_text",
                        ctx=ast.Load(),
                    ),
                    args=[
                        ast.Name(id=element.name, ctx=ast.Load()),
                        ast.Constant(value=element.content),
                    ],
                    keywords=[],
                )
            )
        )
        # TODO: implement logic for combinations of Text and Element children
        return result, event_listeners

    for attr in element.attributes:
        key = attr.name
        if not is_directive(key):
            if element.is_component:
                continue
            result.append(ast_set_attribute(element, key, attr.value))
        elif key.startswith((DIRECTIVE_BIND, ":")):
            if key == DIRECTIVE_BIND:
                # TODO: bind complete dicts
                pass
            else:
                if element.name is None:
                    continue
                result.append(
                    ast_set_dynamic_attribute(
                        element, key, attr.value, analysis["will_use_in_template"]
                    )
                )
        elif key.startswith(("@", DIRECTIVE_ON)):
            result.append(
                ast_add_event_listener(
                    element, key, attr.value, analysis["will_use_in_template"]
                )
            )
            event_listeners.append((element.name, key, attr.value))

    return result, event_listeners


def unfold_dynamic_attribute_value(value, symbols: set):
    expression = value.content

    # Figure out whether one of the global scope functions is referenced
    # Adjust the ast of the expression to use that value instead
    ContextTransformer(symbols=symbols).visit(expression)
    return expression.body


def ast_set_dynamic_attribute(element: Element, key: str, value, symbols: set):
    _, key = key.split(":")
    expression = value.content

    # Figure out whether one of the global scope functions is referenced
    # Adjust the ast of the expression to use that value instead
    ContextTransformer(symbols=symbols).visit(expression)

    return ast.Expr(
        value=ast.Call(
            func=ast.Attribute(
                value=ast.Name(id="renderer", ctx=ast.Load()),
                attr="set_attribute",
                ctx=ast.Load(),
            ),
            args=[
                ast.Name(id=element.name, ctx=ast.Load()),
                ast.Constant(value=key),
                expression.body,
            ],
            keywords=[],
        )
    )


class NodeInvalidatorWrapper(ast.NodeTransformer):
    def __init__(self, nodes):
        super().__init__()
        self.nodes = nodes
        self.parents = []
        self.parent = None

    def generic_visit(self, node):
        result = []
        targets = []
        if hasattr(node, "target"):
            targets = [node.target]
        elif hasattr(node, "targets"):
            targets = node.targets

        for target in targets:
            if target not in self.nodes:
                continue

            elements = target.elts if isinstance(target, ast.Tuple) else [target]
            for element in elements:
                result.append(
                    ast.Expr(
                        value=ast.Call(
                            func=ast.Name(id="__invalidate", ctx=ast.Load()),
                            args=[
                                ast.Constant(value=element.id),
                                ast.Name(id=element.id, ctx=ast.Load()),
                            ],
                            keywords=[],
                        )
                    )
                )

        self.parents.append(node)
        self.parent = node
        try:
            subtree = super().generic_visit(node)
            if result:
                if isinstance(result, list):
                    return [subtree, *result]
                return [subtree, result]
            return subtree
        finally:
            self.parents.remove(node)
            self.parent = self.parents[-1] if self.parents else None


class GlobalToNonLocal(ast.NodeTransformer):
    def visit_Global(self, node):
        return ast.Nonlocal(names=node.names)


# def ast_set_attribute(el: str, key: str, value: str | None):
def ast_set_attribute(element: Element | Text, key: str, value):
    assert isinstance(element, (Element, Text))
    return ast.Expr(
        value=ast.Call(
            func=ast.Attribute(
                value=ast.Name(id="renderer", ctx=ast.Load()),
                attr="set_attribute",
                ctx=ast.Load(),
            ),
            args=[
                ast.Name(id=element.name, ctx=ast.Load()),
                ast.Constant(value=key),
                ast.Constant(value=value if value is not None else True),
            ],
            keywords=[],
        )
    )


def ast_add_event_listener(element: Element, key: str, value, symbols: set):
    assert isinstance(element, Element)
    split_char = "@" if key.startswith("@") else ":"
    _, key = key.split(split_char)

    expression_ast = value.content

    ContextTransformer(symbols=symbols).visit(expression_ast)

    return ast.Expr(
        value=ast.Call(
            func=ast.Attribute(
                value=ast.Name(id="renderer", ctx=ast.Load()),
                attr="add_event_listener",
                ctx=ast.Load(),
            ),
            args=[
                ast.Name(id=element.name, ctx=ast.Load()),
                ast.Constant(value=key),
                expression_ast.body,
            ],
            keywords=[],
        )
    )


def ast_remove_event_listener(el: str, key: str, value, symbols: set):
    expression_ast = value.content
    return ast.Expr(
        value=ast.Call(
            func=ast.Attribute(
                value=ast.Name(id="renderer", ctx=ast.Load()),
                attr="remove_event_listener",
                ctx=ast.Load(),
            ),
            args=[
                ast.Name(id=el, ctx=ast.Load()),
                ast.Constant(value=key),
                expression_ast.body,
            ],
            keywords=[],
        )
    )


class ContextTransformer(ast.NodeTransformer):
    def __init__(self, symbols):
        super().__init__()
        self.symbols = symbols

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            if node.id in self.symbols:
                return ast.Subscript(
                    value=ast.Name(id="context", ctx=ast.Load()),
                    slice=ast.Constant(value=node.id),
                    ctx=ast.Load(),
                )

        return node
