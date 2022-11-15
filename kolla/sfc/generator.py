import ast

from .analyser import Expression, ScopeFinder
from .parser import DIRECTIVE_BIND, DIRECTIVE_ON, Element, Text, is_directive
from .utils import (
    GlobalToNonLocal,
    RemoveImports,
    SymbolsFromContext,
    WrapWithGetFromProps,
    WrapWithInvalidateCall,
)


def generate(tree, analysis, class_name):
    # Process tree
    fragment_functions = []
    ast_create_fragment_function(tree, analysis, fragment_functions)

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

    remove_imports = RemoveImports(imports=analysis["scope"].imports)
    remove_imports.visit(instance_function)

    module = ast.Module(
        body=[
            # Import some runtime dependencies
            ast.ImportFrom(
                module="kolla.runtime",
                names=[
                    ast.alias(name="Component"),
                    ast.alias(name="create_component"),
                    ast.alias(name="destroy_component"),
                    ast.alias(name="Fragment"),
                    ast.alias(name="mount_component"),
                ],
                level=0,
            ),
            # Import all imports from the script
            *analysis["scope"].imports,
            *fragment_functions,
            instance_function,
            class_tree,
        ],
        type_ignores=[],
    )
    return module


def ast_create_fragment_function(tree, analysis, result):
    # items = []

    flatten_tree_into_list_of_elements(tree, items := [])

    components = [item for item in items if item.is_component]
    elements = [item for item in items if not item.is_component]

    element_declarations = [
        ast.Assign(
            targets=[ast.Name(id=item.name, ctx=ast.Store())],
            value=ast.Constant(value=None),
        )
        for item in elements
    ]

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
                        value=props_for_component_init(item, analysis["variables"]),
                    )
                ],
            ),
        )
        for item in components
    ]

    element_creations = [
        ast.Assign(
            targets=[ast.Name(id=item.name, ctx=ast.Store())],
            value=call_create_element(item),
        )
        for item in elements
    ]

    component_creations = [call_create_component(item) for item in components]

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

    # Mounts need to be processed in the order that they appear in the template
    mounts = [mount_element(item) for item in items]

    element_updates = []
    component_updates = [
        ast.Assign(
            targets=[ast.Name(id=f"{item.name}_changes", ctx=ast.Store())],
            value=ast.Dict(keys=[], values=[]),
        )
        for item in components
    ]

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

    component_updates.extend(
        [
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
            for item in components
        ]
    )

    if not element_updates and not component_updates:
        element_updates.append(ast.Pass())

    nonlocal_statement = [ast.Nonlocal(names=list([item.name for item in elements]))]
    if not nonlocal_statement[0].names:
        nonlocal_statement = [ast.Pass()]

    def destroy_element(element):
        if element.is_component:
            return ast.Expr(
                value=ast.Call(
                    func=ast.Name(id="destroy_component", ctx=ast.Load()),
                    args=[ast.Name(id=element.name, ctx=ast.Load())],
                    keywords=[],
                ),
            )
        return ast.Expr(
            value=ast.Call(
                func=ast.Attribute(
                    value=ast.Name(id="renderer", ctx=ast.Load()),
                    attr="remove",
                    ctx=ast.Load(),
                ),
                args=[
                    ast.Name(id=element.name, ctx=ast.Load()),
                    ast.Name(
                        id="__parent" if not element.parent else element.parent.name,
                        ctx=ast.Load(),
                    ),
                ],
                keywords=[],
            ),
        )

    item_destroys = [destroy_element(item) for item in items]
    item_undeclarations = [
        ast.Assign(
            targets=[ast.Name(id=item.name, ctx=ast.Store())],
            value=ast.Constant(value=None),
        )
        for item in items
    ]

    result.append(
        ast.FunctionDef(
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
                        *nonlocal_statement,
                        *item_destroys,
                        *remove_event_listeners,
                        *item_undeclarations,
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

    invalidator_wrapper = WrapWithInvalidateCall(wrapped_nodes)
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

        WrapWithGetFromProps(scope_finder.globals).visit(script_tree)

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
    SymbolsFromContext(symbols=symbols).visit(expression)
    return expression.body


def ast_set_dynamic_attribute(element: Element, key: str, value, symbols: set):
    _, key = key.split(":")
    expression = value.content

    # Figure out whether one of the global scope functions is referenced
    # Adjust the ast of the expression to use that value instead
    SymbolsFromContext(symbols=symbols).visit(expression)

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

    SymbolsFromContext(symbols=symbols).visit(expression_ast)

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


def call_create_component(component):
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


def flatten_tree_into_list_of_elements(element, result):
    if isinstance(element, (Element, Text)):
        result.append(element)

    if hasattr(element, "children"):
        for child in element.children:
            flatten_tree_into_list_of_elements(child, result)


def props_for_component_init(component, variables):
    keys = []
    values = []

    for attr in component.attributes:
        if isinstance(attr.value, Expression):
            val = unfold_dynamic_attribute_value(attr.value, variables)
        else:
            val = ast.Constant(value=attr.value)
        keys.append(ast.Constant(value=attr.key))
        values.append(val)

    return ast.Dict(keys=keys, values=values)


def call_create_element(element):
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


def mount_element(item):
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
