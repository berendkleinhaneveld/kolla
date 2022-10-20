import ast
import textwrap
from pathlib import Path

import ast_scope

DIRECTIVE_PREFIX = "v-"
DIRECTIVE_BIND = f"{DIRECTIVE_PREFIX}bind"
DIRECTIVE_IF = f"{DIRECTIVE_PREFIX}if"
DIRECTIVE_ELSE_IF = f"{DIRECTIVE_PREFIX}else-if"
DIRECTIVE_ELSE = f"{DIRECTIVE_PREFIX}else"
CONTROL_FLOW_DIRECTIVES = (DIRECTIVE_IF, DIRECTIVE_ELSE_IF, DIRECTIVE_ELSE)
DIRECTIVE_FOR = f"{DIRECTIVE_PREFIX}for"
DIRECTIVE_ON = f"{DIRECTIVE_PREFIX}on"


def is_directive(key: str):
    return key.startswith((DIRECTIVE_PREFIX, ":", "@"))


def ast_set_attributes(attributes: dict, symbols: set):
    result = []

    for key, value in attributes.items():
        if not is_directive(key):
            result.append(ast_set_attribute(key, value))
        elif key.startswith((DIRECTIVE_BIND, ":")):
            if key == DIRECTIVE_BIND:
                # TODO: bind complete dicts
                pass
            else:
                result.append(ast_set_dynamic_attribute(key, value, symbols))
        elif key.startswith(("@", DIRECTIVE_ON)):
            result.append(ast_add_event_listener(key, value, symbols))

    return result


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


def ast_set_dynamic_attribute(key: str, value, symbols: set):
    # TODO: keep track of which variables are used in the expressions
    # Because those variables will need to be updated in the `update` function
    _, key = key.split(":")
    expression = ast.parse(value, mode="eval")

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
                ast.Name(id="__element", ctx=ast.Load()),
                ast.Constant(value=key),
                expression.body,
            ],
            keywords=[],
        )
    )


def ast_set_attribute(key: str, value: str | None):
    return ast.Expr(
        value=ast.Call(
            func=ast.Attribute(
                value=ast.Name(id="renderer", ctx=ast.Load()),
                attr="set_attribute",
                ctx=ast.Load(),
            ),
            args=[
                ast.Name(id="__element", ctx=ast.Load()),
                ast.Constant(value=key),
                ast.Constant(value=value if value is not None else True),
            ],
            keywords=[],
        )
    )


def ast_add_event_listener(key: str, value, symbols: set):
    split_char = "@" if key.startswith("@") else ":"
    _, key = key.split(split_char)

    expression_ast = ast.parse(value, mode="eval")

    ContextTransformer(symbols=symbols).visit(expression_ast)

    return ast.Expr(
        value=ast.Call(
            func=ast.Attribute(
                value=ast.Name(id="renderer", ctx=ast.Load()),
                attr="add_event_listener",
                ctx=ast.Load(),
            ),
            args=[
                ast.Name(id="__element", ctx=ast.Load()),
                ast.Constant(value=key),
                expression_ast.body,
            ],
            keywords=[],
        )
    )


def ast_remove_event_listeners(attributes):
    result = []
    for key, value in attributes.items():
        if key.startswith((DIRECTIVE_ON, "@")):
            expression_ast = ast.parse(value, mode="eval")
            result.append(
                ast.Expr(
                    value=ast.Call(
                        func=ast.Attribute(
                            value=ast.Name(id="renderer", ctx=ast.Load()),
                            attr="remove_event_listener",
                            ctx=ast.Load(),
                        ),
                        args=[
                            ast.Name(id="__element", ctx=ast.Load()),
                            ast.Constant(value=key),
                            expression_ast.body,
                        ],
                        keywords=[],
                    )
                )
            )
    return result


def ast_create_fragment_function(tag: str, attributes: dict, symbols: set):
    """Fragment for 'normal' tags without v-if or v-for statements"""
    # TODO: figure out how to handle 'template' and 'component :is' tags

    return ast.FunctionDef(
        name="create_fragment",
        args=ast.arguments(
            posonlyargs=[],
            args=[
                ast.arg(
                    arg="context",
                    annotation=ast.Name(id="dict", ctx=ast.Load()),
                ),
                ast.arg(
                    arg="renderer",
                    annotation=ast.Name(
                        id="Renderer",
                        ctx=ast.Load(),
                    ),
                ),
            ],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[],
        ),
        body=[
            # Declare the element variable
            ast.Assign(
                targets=[ast.Name(id="__element", ctx=ast.Store())],
                value=ast.Constant(value=None),
            ),
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
                    ast.Nonlocal(names=["__element"]),
                    ast.Assign(
                        targets=[ast.Name(id="__element", ctx=ast.Store())],
                        value=ast.Call(
                            func=ast.Attribute(
                                value=ast.Name(id="renderer", ctx=ast.Load()),
                                attr="create_element",
                                ctx=ast.Load(),
                            ),
                            args=[ast.Constant(value=tag)],
                            keywords=[],
                        ),
                    ),
                    *ast_set_attributes(attributes, symbols),
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
                    ast.Assign(
                        targets=[ast.Name(id="__parent", ctx=ast.Store())],
                        value=ast.Name(id="parent", ctx=ast.Load()),
                    ),
                    ast.Expr(
                        value=ast.Call(
                            func=ast.Attribute(
                                value=ast.Name(id="renderer", ctx=ast.Load()),
                                attr="insert",
                                ctx=ast.Load(),
                            ),
                            args=[
                                ast.Name(id="__element", ctx=ast.Load()),
                                ast.Name(id="parent", ctx=ast.Load()),
                                ast.Name(id="anchor", ctx=ast.Load()),
                            ],
                            keywords=[],
                        ),
                    ),
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
                # TODO: implement update logic
                body=[ast.Pass()],
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
                    *ast_remove_event_listeners(attributes),
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


class GlobalToNonLocal(ast.NodeTransformer):
    def visit_Global(self, node):
        return ast.Nonlocal(names=node.names)


class NodeInvalidatorFinder(ast.NodeVisitor):
    def __init__(self, scope_info):
        super().__init__()
        self.depth = 0
        self.scope_info = scope_info
        # FIXME: make sure to only get stuff that is assigned in global scope
        # self.variables = scope_info.global_scope.variables.variables
        self.nodes = []

    def generic_visit(self, node):
        self.depth += 1
        # Magic nr 3! (3 is level of assignment of name in global scope)
        if hasattr(node, "ctx") and isinstance(node.ctx, ast.Store) and self.depth > 3:
            self.nodes.append(node)
        super().generic_visit(node)
        self.depth -= 1


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


def ast_instance_function(script_tree):
    scope_info = ast_scope.annotate(script_tree)

    # First traverse the tree to find the assignment nodes
    # Then traverse again to find the parents of those nodes and
    # insert the invalidate call right after the assignment calls
    invalidator_finder = NodeInvalidatorFinder(scope_info)
    invalidator_finder.visit(script_tree)

    invalidator_wrapper = NodeInvalidatorWrapper(invalidator_finder.nodes)
    invalidator_wrapper.visit(script_tree)

    symbols = [
        ast.Constant(value=symbol)
        for symbol in scope_info.global_scope.symbols_in_frame
    ]

    symbol_refs = [ast.Name(id=name.value, ctx=ast.Load()) for name in symbols]

    # This might be a bit hacky? But I think it actually works
    GlobalToNonLocal().visit(script_tree)

    return (
        ast.FunctionDef(
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
        ),
        scope_info.global_scope.symbols_in_frame,
    )


def ast_create_component_class():
    file_name = Path(__file__).stem
    file_name_parts = [part.capitalize() for part in file_name.split("_")]
    class_name = "".join(file_name_parts)
    """
    def __init__(self, options):
        super().__init__()
        self.init(options, instance, create_fragment)
    """
    return class_name, ast.ClassDef(
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


def pretty_code_print(tree):  # pragma: no cover
    """Handy function for debugging an ast tree"""
    plain_result = ast.unparse(tree)

    try:
        import black

        result = black.format_file_contents(
            plain_result, fast=False, mode=black.mode.Mode()
        )
    except ImportError:
        pass

    try:
        from rich.console import Console
        from rich.syntax import Syntax

        console = Console()
    except ImportError:
        print(plain_result)
        return

    try:
        result = black.format_file_contents(
            plain_result, fast=False, mode=black.mode.Mode()
        )
    except black.parsing.InvalidInput:
        result = plain_result
        return

    syntax = Syntax(result, "python")
    console.print(syntax)


if __name__ == "__main__":
    code = """
        count = 0
        foo = "foo"
        bar = "bar"
        # state = {}


        def bump():
            global count
            count += 1
            # state["count"] = count

        def reset():
            global count
            count = 0
            foo, bar = bar, foo
    """
    script_tree = ast.parse(textwrap.dedent(code), mode="exec")

    instance_function, symbols = ast_instance_function(script_tree)

    tree = ast_create_fragment_function(
        "item",
        {
            "value": "foo",
            ":bar": "20",
            ":count": "count",
            "visible": None,
            "@click": "bump",
        },
        symbols,
    )

    class_name, class_tree = ast_create_component_class()

    module = ast.Module(
        body=[
            # Import some stuff
            ast.ImportFrom(
                module="kolla",
                names=[
                    ast.alias(name="Component"),
                    ast.alias(name="Block"),
                    ast.alias(name="Renderer"),
                ],
                level=0,
            ),
            tree,
            instance_function,
            class_tree,
        ],
        type_ignores=[],
    )
    ast.fix_missing_locations(module)

    pretty_code_print(module)

    # Compile the tree into a code object (module)
    code = compile(module, filename="none", mode="exec")
    # Execute the code as module and pass a dictionary that will capture
    # the global and local scope of the module
    module_namespace = {}
    exec(code, module_namespace)

    # Check that the class definition is an actual subclass of Component
    component_class = module_namespace[class_name]

    target = {}
    options = {"target": target}

    component_instance = component_class(options)
    print(component_instance)
    print(target)
