import ast
from collections import defaultdict

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

    # Rewrite the script as 'instance' method
    module = ast.Module(
        body=[
            # Import some stuff
            ast.ImportFrom(
                module="kolla.runtime",
                names=[
                    ast.alias(name="Component"),
                    ast.alias(name="Block"),
                ],
                level=0,
            ),
            fragment_function,
            instance_function,
            class_tree,
            # TODO: insert if __name__ == "__main__": part to make file runnable?
        ],
        type_ignores=[],
    )
    return module


def ast_create_fragment_function(tree, analysis):
    elements = {}

    def gather_tags(element):
        if isinstance(element, Element):
            elements[numbered_tag(element.name)] = element
        if isinstance(element, Text):
            elements[numbered_tag("text")] = element

        if hasattr(element, "children"):
            for child in element.children:
                gather_tags(child)

    gather_tags(tree)

    element_declarations = [
        ast.Assign(
            targets=[ast.Name(id=el, ctx=ast.Store())],
            value=ast.Constant(value=None),
        )
        for el in elements
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
            args=[ast.Constant(value=element.name)],
            keywords=[],
        )

    element_creations = [
        ast.Assign(
            targets=[ast.Name(id=el, ctx=ast.Store())],
            value=create_call_for_element(element),
        )
        for el, element in elements.items()
    ]
    element_set_attributes = []
    remove_event_listeners = []
    for el, element in elements.items():
        set_attributes, event_listeners = ast_set_attributes(el, element, analysis)
        element_set_attributes.extend(set_attributes)
        remove_event_listeners.extend(
            [
                ast_remove_event_listener(*event_listener, analysis)
                for event_listener in event_listeners
            ]
        )

    def element_name(element):
        for el, instance in elements.items():
            if element == instance:
                return el

    element_mounts = [
        ast.Expr(
            value=ast.Call(
                func=ast.Attribute(
                    value=ast.Name(id="renderer", ctx=ast.Load()),
                    attr="insert",
                    ctx=ast.Load(),
                ),
                args=[
                    ast.Name(id=el, ctx=ast.Load()),
                    ast.Name(
                        id="parent"
                        if element.parent is None
                        else element_name(element.parent),
                        ctx=ast.Load(),
                    ),
                    ast.Name(id="anchor", ctx=ast.Load()),
                ],
                keywords=[],
            ),
        )
        for el, element in elements.items()
    ]

    element_updates = []
    for name in analysis["will_change"]:
        for element, attr in analysis["will_change_elements"][name]:
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
                            element_name(element),
                            attr.name,
                            attr.value,
                            analysis["variables"],
                        )
                    ],
                    orelse=[],
                )
            )
    if not element_updates:
        element_updates.append(ast.Pass())

    nonlocal_statement = [ast.Pass()]
    if list(elements):
        nonlocal_statement = [ast.Nonlocal(names=list(elements))]

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
                    *element_mounts,
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
                body=[*element_updates],
                decorator_list=[],
            ),
            ast.FunctionDef(
                name="unmount",
                args=ast.arguments(
                    posonlyargs=[],
                    args=[],
                    kwonlyargs=[],
                    kw_defaults=[],
                    defaults=[],
                ),
                body=[
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
                    func=ast.Name(id="Block", ctx=ast.Load()),
                    args=[
                        ast.Name(id="create", ctx=ast.Load()),
                        ast.Name(id="mount", ctx=ast.Load()),
                        ast.Name(id="update", ctx=ast.Load()),
                        ast.Name(id="unmount", ctx=ast.Load()),
                    ],
                    keywords=[],
                )
            ),
        ],
        decorator_list=[],
        returns=ast.Name(id="Block", ctx=ast.Load()),
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
                    ],
                    kwonlyargs=[],
                    kw_defaults=[],
                    defaults=[ast.Constant(value=None)],
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
                            keywords=[],
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

    # A component script is written at module level, but instead it will
    # be instantiated and run within a function scope. Hence, the global
    # scope will have to be updated to nonlocal instead.
    GlobalToNonLocal().visit(script_tree)

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


counter = defaultdict(int)


def numbered_tag(tag):
    count = counter[tag]
    counter[tag] += 1
    return f"{tag}_{count}"


def ast_set_attributes(el: str, element: Element, analysis):
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
                        ast.Name(id=el, ctx=ast.Load()),
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
            result.append(ast_set_attribute(el, key, attr.value))
        elif key.startswith((DIRECTIVE_BIND, ":")):
            if key == DIRECTIVE_BIND:
                # TODO: bind complete dicts
                pass
            else:
                result.append(
                    ast_set_dynamic_attribute(
                        el, key, attr.value, analysis["will_use_in_template"]
                    )
                )
        elif key.startswith(("@", DIRECTIVE_ON)):
            result.append(
                ast_add_event_listener(
                    el, key, attr.value, analysis["will_use_in_template"]
                )
            )
            event_listeners.append((el, key, attr.value))

    return result, event_listeners


def ast_set_dynamic_attribute(el: str, key: str, value, symbols: set):
    # TODO: keep track of which variables are used in the expressions
    # Because those variables will need to be updated in the `update` function
    _, key = key.split(":")
    # expression = ast.parse(value, mode="eval")
    expression = value.content

    # figure out whether one of the global scope functions is referenced
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
                ast.Name(id=el, ctx=ast.Load()),
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


def ast_set_attribute(el: str, key: str, value: str | None):
    return ast.Expr(
        value=ast.Call(
            func=ast.Attribute(
                value=ast.Name(id="renderer", ctx=ast.Load()),
                attr="set_attribute",
                ctx=ast.Load(),
            ),
            args=[
                ast.Name(id=el, ctx=ast.Load()),
                ast.Constant(value=key),
                ast.Constant(value=value if value is not None else True),
            ],
            keywords=[],
        )
    )


def ast_add_event_listener(el: str, key: str, value, symbols: set):
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
                ast.Name(id=el, ctx=ast.Load()),
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
