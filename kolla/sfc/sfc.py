import ast
from collections import defaultdict
from html.parser import HTMLParser
import logging
from pathlib import Path
import re
import sys

# import inspect

from kolla import Component


logger = logging.getLogger(__name__)


# Adjust this setting to disable some runtime checks
# Defaults to True, except when it is part of an installed application
KOLLA_RUNTIME_WARNINGS = not getattr(sys, "frozen", False)

SUFFIX = "kolla"
DIRECTIVE_PREFIX = "v-"
DIRECTIVE_BIND = f"{DIRECTIVE_PREFIX}bind"
DIRECTIVE_IF = f"{DIRECTIVE_PREFIX}if"
DIRECTIVE_ELSE_IF = f"{DIRECTIVE_PREFIX}else-if"
DIRECTIVE_ELSE = f"{DIRECTIVE_PREFIX}else"
CONTROL_FLOW_DIRECTIVES = (DIRECTIVE_IF, DIRECTIVE_ELSE_IF, DIRECTIVE_ELSE)
DIRECTIVE_FOR = f"{DIRECTIVE_PREFIX}for"
DIRECTIVE_ON = f"{DIRECTIVE_PREFIX}on"
AST_GEN_VARIABLE_PREFIX = "_ast_"

COMPONENT_CLASS_DEFINITION = re.compile(r"class\s*(.*?)\s*\(.*?\)\s*:")
MOUSTACHES = re.compile(r"\{\{.*?\}\}")


def load(path):
    """
    Loads and returns a component from a .kolla file.

    A subclass of Component will be created from the .kolla file
    where the contents of the <template> tag will be used as
    the `render` function, while the contents of the <script>
    tag will be used to provide the rest of the functions of
    the component.

    For example:

        <template>
          <item foo="bar">
            <item baz="bla"/>
          </item>
        </template

        <script>
        import kolla

        class Foo(kolla.Component):
            pass
        </script>

    """
    template = path.read_text()

    return load_from_string(template, path)


def load_from_string(template, path=None):
    """
    Load template from a string.
    Returns tuple of class definition and module namespace.
    """
    if path is None:
        path = "<template>"

    # Construct the AST tree
    tree, name = construct_ast(path=path, template=template)

    # Compile the tree into a code object (module)
    code = compile(tree, filename=str(path), mode="exec")
    # Execute the code as module and pass a dictionary that will capture
    # the global and local scope of the module
    module_namespace = {}
    exec(code, module_namespace)

    # Check that the class definition is an actual subclass of Component
    component_class = module_namespace[name]
    if not issubclass(component_class, Component):
        raise ValueError(
            f"The last class defined in {path} is not a subclass of "
            f"Component: {component_class}"
        )
    return component_class, module_namespace


def construct_ast(path, template=None):
    """
    Returns a tuple of the constructed AST tree and name of (enhanced) component class.

    Construct an AST from the .kolla file by first creating an AST from the script tag,
    and then compile the contents of the template tag and insert that into the component
    class definition as `render` function.
    """
    if not template:
        template = Path(path).read_text()

    # Parse the file component into a tree of Node instances
    parser = KollaParser()
    parser.feed(template)

    # Get the AST from the script tag
    script_tree = get_script_ast(parser, path)

    # Find a list of imported names (or aliases, if any)
    # Those names don't have to be wrapped by `_lookup`
    imported_names = ImportsCollector()
    imported_names.visit(script_tree)

    class_names = set(
        node.name for node in script_tree.body if isinstance(node, ast.ClassDef)
    )

    # Find the last ClassDef and assume that it is the
    # component that is defined in the SFC
    component_def = None
    for node in reversed(script_tree.body):
        if isinstance(node, ast.ClassDef):
            component_def = node
            break

    # Remove the script tag from the tree and process the rest
    script_node = parser.root.child_with_tag("script")
    parser.root.children.remove(script_node)

    # Create render function as AST and inject into the ClassDef
    # render_tree = create_ast_render_function(
    render_tree = create_kolla_render_function(
        parser.root, names=imported_names.names | class_names
    )
    ast.fix_missing_locations(render_tree)

    try:
        _print_ast_tree_as_code(render_tree)
    except Exception as e:
        logger.warning("Could not unparse AST", exc_info=e)

    # Put location of render function outside of the script tag
    # This makes sure that the render function can be excluded
    # from linting.
    # Note that it's still possible to put code after the component
    # class at the end of the script node.
    line, _ = script_node.end
    ast.increment_lineno(render_tree, n=line)
    component_def.body.append(render_tree)

    # Because we modified the AST significantly we need to call an AST
    # method to fix any `lineno` and `col_offset` attributes of the nodes
    ast.fix_missing_locations(script_tree)
    return script_tree, component_def.name


def get_script_ast(parser, path):
    """
    Returns the AST created from the script tag in the .kolla file.
    """
    # Read the data from script block
    script_node = parser.root.child_with_tag("script")
    script = script_node.data
    line, _ = script_node.location

    # Create an AST from the script
    script_tree = ast.parse(script, filename=str(path), mode="exec")
    # Make sure that the lineno's match up with the lines in the .kolla file
    ast.increment_lineno(script_tree, n=line)
    return script_tree


def ast_create_fragment(el, tag, is_component, parent=None):
    """
    Return AST for creating an element with `tag` and
    assigning it to variable name: `el`
    """

    keywords = [
        ast.keyword(
            arg="tag",
            value=ast.Name(id=tag, ctx=ast.Load())
            if is_component
            else ast.Constant(value=tag),
        ),
    ]
    if parent is not None:
        keywords.append(
            ast.keyword(arg="parent", value=ast.Name(id=parent, ctx=ast.Load()))
        )
    return ast.Assign(
        targets=[ast.Name(id=el, ctx=ast.Store())],
        value=ast.Call(
            func=ast.Name(
                id="ComponentFragment" if is_component else "Fragment", ctx=ast.Load()
            ),
            args=[
                ast.Name(id="renderer", ctx=ast.Load()),
            ],
            keywords=keywords,
        ),
    )


def ast_set_attribute(el, key, value):
    return ast.Expr(
        value=ast.Call(
            func=ast.Attribute(
                value=ast.Name(id=el, ctx=ast.Load()),
                attr="set_attribute",
                ctx=ast.Load(),
            ),
            args=[ast.Constant(value=key), ast.Constant(value=value)],
            keywords=[],
        )
    )


def ast_set_dynamic_type(el, value, names):
    source = ast.parse(f"{el}.set_type(lambda: {value})", mode="eval")
    lambda_names = LambdaNamesCollector()
    lambda_names.visit(source)
    return ast.Expr(
        value=(
            RewriteName(
                skip={"renderer", "new", el, "watch"} | lambda_names.names | names
            )
            .visit(source)
            .body
        )
    )


def ast_set_bind(el, key, value, names):
    _, key = key.split(":")
    source = ast.parse(f'{el}.set_bind("{key}", lambda: {value})', mode="eval")
    lambda_names = LambdaNamesCollector()
    lambda_names.visit(source)
    return ast.Expr(
        value=(
            RewriteName(
                skip={"renderer", "new", el, "watch"} | lambda_names.names | names
            )
            .visit(source)
            .body
        )
    )


def ast_set_bind_dict(el, value, names):
    source = ast.parse(f"{el}.set_bind_dict('{value}', lambda: {value})", mode="eval")
    return ast.Expr(
        value=(
            RewriteName(skip={"renderer", "new", el, "watch"} | names)
            .visit(source)
            .body
        )
    )


def ast_set_event(el, key, value, names):
    split_char = "@" if key.startswith("@") else ":"
    _, key = key.split(split_char)

    expression_ast = ast.parse(
        f"lambda *args, **kwargs: {value}(*args, **kwargs)", mode="eval"
    )
    # v-on directives allow for lambdas which define arguments
    # which need to be skipped by the RewriteName visitor
    lambda_names = LambdaNamesCollector()
    lambda_names.visit(expression_ast)
    RewriteName(skip={"args", "kwargs"} | lambda_names.names | names).visit(
        expression_ast
    )

    return ast.Expr(
        value=ast.Call(
            func=ast.Attribute(
                value=ast.Name(id=el, ctx=ast.Load()),
                attr="set_event",
                ctx=ast.Load(),
            ),
            args=[
                ast.Constant(value=key),
                expression_ast.body,
            ],
            keywords=[],
        )
    )


def ast_set_condition(child, condition, names):
    condition_ast = ast.parse(f"lambda: bool({condition})", mode="eval")
    RewriteName(skip=names).visit(condition_ast)

    return ast.Expr(
        value=ast.Call(
            func=ast.Attribute(
                value=ast.Name(id=child, ctx=ast.Load()),
                attr="set_condition",
                ctx=ast.Load(),
            ),
            args=[condition_ast.body],
            keywords=[],
        )
    )


def ast_create_control_flow(name, parent):
    return ast.Assign(
        targets=[ast.Name(id=name, ctx=ast.Store())],
        value=ast.Call(
            func=ast.Name(id="ControlFlowFragment", ctx=ast.Load()),
            args=[
                ast.Name(id="renderer", ctx=ast.Load()),
            ],
            keywords=[
                ast.keyword(
                    arg="parent",
                    value=ast.Name(id=parent, ctx=ast.Load()),
                )
            ],
        ),
    )


def ast_create_list_fragment(name, parent, expression):
    # TODO: figure out how to treat the expression
    return ast.Assign(
        targets=[ast.Name(id=name, ctx=ast.Store())],
        value=ast.Call(
            func=ast.Name(id="ListFragment", ctx=ast.Load()),
            args=[
                ast.Name(id="renderer", ctx=ast.Load()),
            ],
            keywords=[
                ast.keyword(
                    arg="parent",
                    value=ast.Name(id=parent, ctx=ast.Load()),
                )
            ],
        ),
    )


def create_kolla_render_function(node, names):
    body: list[ast.Assign | ast.Expr | ast.Return] = []
    body.append(
        ast.ImportFrom(
            module="observ",
            names=[ast.alias(name="watch")],
            level=0,
        )
    )
    body.append(
        ast.ImportFrom(
            module="kolla.fragment",
            names=[
                # TODO: import only the needed items
                ast.alias(name="ControlFlowFragment"),
                ast.alias(name="ComponentFragment"),
                ast.alias(name="ListFragment"),
                ast.alias(name="Fragment"),
            ],
            level=0,
        )
    )

    body.append(
        ast.Assign(
            targets=[ast.Name(id="component", ctx=ast.Store())],
            value=ast.Call(
                func=ast.Name(id="ComponentFragment", ctx=ast.Load()),
                args=[
                    ast.Name(id="renderer", ctx=ast.Load()),
                ],
                keywords=[],
            ),
        )
    )

    counter = defaultdict(int)

    def create_fragments_function(
        node: Node, targets: ast.Name | ast.Tuple, names: set
    ):
        name = f"create_{node.tag}"
        # FIXME: naming the return obj is a bit shaky...
        return_stmt = ast.Return(
            value=ast.Name(id=f"{node.tag}{counter[node.tag]}", ctx=ast.Load())
        )

        unpack_context = ast.Assign(
            targets=[targets],
            value=ast.Name(id="context", ctx=ast.Load()),
        )

        names_collector = StoredNameCollector()
        names_collector.visit(targets)
        unpacked_names = names_collector.names

        # TODO: add 'ctx' argument in order to pass context to the create_node method
        function = ast.FunctionDef(
            name=name,
            args=ast.arguments(
                posonlyargs=[],
                args=[ast.arg("context")],
                kwonlyargs=[],
                kw_defaults=[],
                defaults=[],
            ),
            # TODO: parse the v-for expression and create an ast loop
            # over those items to create Fragments on the fly
            body=[
                unpack_context,
                *create_children(
                    [node],
                    None,
                    names=names | unpacked_names,
                    within_for_loop=True,
                ),
            ],
            decorator_list=[],
            returns=None,
        )
        function.body.append(return_stmt)

        return name, function

    def create_patch_function(node: Node, targets: ast.Name | ast.Tuple, names: set):
        name = f"patch_{node.tag}"

        unpack_context = ast.Assign(
            targets=[targets],
            value=ast.Name(id="context", ctx=ast.Load()),
        )

        names_collector = StoredNameCollector()
        names_collector.visit(targets)
        unpacked_names = names_collector.names

        function = ast.FunctionDef(
            name=name,
            args=ast.arguments(
                posonlyargs=[],
                args=[ast.arg(node.tag), ast.arg("context")],
                kwonlyargs=[],
                kw_defaults=[],
                defaults=[],
            ),
            body=[
                unpack_context,
                *create_children(
                    [node],
                    None,
                    names=names | unpacked_names,
                    within_for_loop=True,
                ),
            ],
            decorator_list=[],
            returns=None,
        )

        return name, function

    # Create and add children
    def create_children(
        nodes: list[Node], target: str, names: set, within_for_loop=False
    ):
        result = []
        control_flow_parent = None
        for child in nodes:
            # Create element name
            el = f"{child.tag}{counter[child.tag]}"
            counter[child.tag] += 1
            parent = target
            if [
                True
                for key in child.attrs
                if key.startswith((DIRECTIVE_IF, DIRECTIVE_ELSE, DIRECTIVE_ELSE_IF))
            ]:
                parent = None

            # Set static attributes and dynamic (bind) attributes
            attributes = []
            events = []
            binds = []
            condition = None

            node_with_list_expression = False
            if not within_for_loop:
                for key in filter(lambda item: item.startswith("v-for"), child.attrs):
                    node_with_list_expression = True
                    # Special v-for node!
                    expression = child.attrs[key]
                    name = f"list{counter['list']}"
                    counter["list"] += 1
                    # Reset any control flow that came before
                    control_flow_parent = None
                    result.append(ast_create_list_fragment(name, parent, expression))
                    expr = f"[None for {expression}]"
                    expression_ast = ast.parse(expr).body[0].value
                    targets = expression_ast.generators[0].target
                    # Set the `target` to None so that the targets don't get
                    # rewritten by the RewriteName NodeTransformer
                    # The NodeTransformer doesn't transform the root node, so
                    # we need to pass in the parent node of the node that we
                    # want to transform which is also the parent node of `target`
                    expression_ast.generators[0].target = None

                    RewriteName(names).visit(expression_ast.generators[0])
                    iterator = expression_ast.generators[0].iter

                    (
                        create_frag_func_name,
                        create_frag_function,
                    ) = create_fragments_function(child, targets, names)
                    patch_func_name, patch_function = create_patch_function(
                        child, targets, names
                    )
                    is_keyed = ":key" in child.attrs
                    result.append(create_frag_function)
                    result.append(patch_function)
                    result.append(
                        ast.Expr(
                            value=ast.Call(
                                func=ast.Attribute(
                                    value=ast.Name(id=name, ctx=ast.Load()),
                                    attr="set_create_fragment",
                                    ctx=ast.Load(),
                                ),
                                args=[
                                    ast.Name(id=create_frag_func_name, ctx=ast.Load()),
                                    ast.Constant(value=is_keyed),
                                ],
                                keywords=[],
                            )
                        )
                    )
                    result.append(
                        ast.Expr(
                            value=ast.Call(
                                func=ast.Attribute(
                                    value=ast.Name(id=name, ctx=ast.Load()),
                                    attr="set_patch_fragment",
                                    ctx=ast.Load(),
                                ),
                                args=[ast.Name(id=patch_func_name, ctx=ast.Load())],
                                keywords=[],
                            )
                        )
                    )

                    iterator_fn = ast.Lambda(
                        args=ast.arguments(
                            posonlyargs=[],
                            args=[],
                            kwonlyargs=[],
                            kw_defaults=[],
                            defaults=[],
                        ),
                        body=iterator,
                    )

                    result.append(
                        ast.Expr(
                            value=ast.Call(
                                func=ast.Attribute(
                                    value=ast.Name(id=name, ctx=ast.Load()),
                                    attr="set_expression",
                                    ctx=ast.Load(),
                                ),
                                args=[iterator_fn],
                                keywords=[],
                            )
                        )
                    )
                    break

            if node_with_list_expression:
                continue

            if control_flow_directive := child.control_flow():
                if control_flow_directive == DIRECTIVE_IF:
                    control_flow_parent = f"control_flow{counter['control_flow']}"
                    counter["control_flow"] += 1
            else:
                # Reset the control flow parent
                control_flow_parent = None

            for key, value in child.attrs.items():
                if not is_directive(key):
                    attributes.append(ast_set_attribute(el, key, value))
                elif key.startswith((DIRECTIVE_BIND, ":")):
                    if key == DIRECTIVE_BIND:
                        # TODO: bind complete dicts
                        binds.append(ast_set_bind_dict(el, value, names))
                    elif key == ":is" and el.startswith("component"):
                        binds.append(ast_set_dynamic_type(el, value, names))
                    else:
                        binds.append(ast_set_bind(el, key, value, names))
                elif key.startswith((DIRECTIVE_ON, "@")):
                    events.append(ast_set_event(el, key, value, names))
                elif key == DIRECTIVE_IF:
                    result.append(ast_create_control_flow(control_flow_parent, target))
                    condition = ast_set_condition(el, value, names)
                elif key == DIRECTIVE_ELSE_IF:
                    condition = ast_set_condition(el, value, names)
                elif key == DIRECTIVE_ELSE:
                    pass

            result.append(
                ast_create_fragment(
                    el,
                    child.tag,
                    is_component=child.tag in names,
                    parent=control_flow_parent or parent,
                )
            )
            if condition:
                result.append(condition)
            result.extend(attributes)
            result.extend(binds)
            result.extend(events)

            # Process the children
            result.extend(create_children(child.children, el, names))

        return result

    body.extend(create_children(node.children, "component", names))

    body.append(ast.Return(value=ast.Name(id="component", ctx=ast.Load())))
    return ast.FunctionDef(
        name="render",
        args=ast.arguments(
            posonlyargs=[],
            args=[ast.arg("self"), ast.arg("renderer")],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[],
        ),
        body=body,
        decorator_list=[],
    )


def is_directive(key):
    return key.startswith((DIRECTIVE_PREFIX, ":", "@"))


class StoredNameCollector(ast.NodeVisitor):
    """AST node visitor that will create a set of the ids of every Name node
    it encounters."""

    def __init__(self):
        self.names = set()

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Store):
            self.names.add(node.id)


class NameCollector(ast.NodeVisitor):
    """AST node visitor that will create a set of the ids of every Name node
    it encounters."""

    def __init__(self):
        self.names = set()

    def visit_Name(self, node):
        self.names.add(node.id)


class LambdaNamesCollector(ast.NodeVisitor):
    def __init__(self):
        self.names = set()

    def visit_Lambda(self, node):
        # For some reason the body of a lambda is not visited
        # so we need to do it manually.
        visitor = LambdaNamesCollector()
        visitor.visit(node.body)
        self.names.update(visitor.names)

        for arg in node.args.posonlyargs + node.args.args + node.args.kwonlyargs:
            self.names.add(arg.arg)


class RewriteName(ast.NodeTransformer):
    """AST node transformer that will try to replace static Name nodes with
    a call to `_lookup` with the name of the node."""

    def __init__(self, skip):
        self.skip = skip

    def visit_Name(self, node):
        # Don't try and replace any item from the __builtins__
        if node.id in __builtins__:
            return node

        # Don't replace any name that should be explicitely skipped
        if node.id in self.skip:
            return node

        return ast.Call(
            func=ast.Attribute(
                value=ast.Name(id="self", ctx=ast.Load()),
                attr="_lookup",
                ctx=ast.Load(),
            ),
            args=[
                ast.Constant(value=node.id),
                ast.Call(
                    func=ast.Name(id="globals", ctx=ast.Load()),
                    args=[],
                    keywords=[],
                ),
            ],
            keywords=[],
        )


class ImportsCollector(ast.NodeVisitor):
    def __init__(self):
        self.names = set()

    def visit_ImportFrom(self, node):
        for alias in node.names:
            self.names.add(alias.asname or alias.name)

    def visit_Import(self, node):
        for alias in node.names:
            self.names.add(alias.asname or alias.name)


class Node:
    """Node that represents an element from a .kolla file."""

    def __init__(self, tag, attrs=None, location=None):
        super().__init__()
        self.tag = tag
        self.attrs = attrs or {}
        self.location = location
        self.end = None
        self.data = None
        self.children = []

    def control_flow(self):
        """Returns the control flow string (if/else-if/else), if present in the
        attrs of the node."""
        for attr in self.attrs:
            if attr in CONTROL_FLOW_DIRECTIVES:
                return attr

    def child_with_tag(self, tag):
        for child in self.children:
            if child.tag == tag:
                return child


class KollaParser(HTMLParser):
    """Parser for .kolla files.

    Creates a tree of Nodes with all encountered attributes and data.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.root = Node("root")
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        # The tag parameter is lower-cased by the HTMLParser.
        # In order to figure out whether the tag indicates
        # an imported class, we need the original casing for
        # the tag.
        # Using the original start tag, we can figure out where
        # the tag is located using a lower-cased version. And then
        # use the index to extract the original casing for the tag.
        complete_tag = self.get_starttag_text()
        index = complete_tag.lower().index(tag)
        original_tag = complete_tag[index : index + len(tag)]
        node = Node(original_tag, dict(attrs), self.getpos())

        # Cast attributes that have no value to boolean (True)
        # so that they function like flags
        for key, value in node.attrs.items():
            # TODO: check if the value should actually be an integer
            if value is None:
                node.attrs[key] = True

        # Add item as child to the last on the stack
        self.stack[-1].children.append(node)
        # Make the new node the last on the stack
        self.stack.append(node)

    def handle_endtag(self, tag):
        # TODO: pop it till popping the same tag in order to
        # work around unclosed tags?
        # Pop the stack
        node = self.stack.pop()
        node.end = self.getpos()

    def handle_data(self, data):
        if data.strip():
            self.stack[-1].data = data.strip()


def _print_ast_tree_as_code(tree):  # pragma: no cover
    """Handy function for debugging an ast tree"""
    try:
        import black
    except ImportError:
        return

    from rich.console import Console
    from rich.syntax import Syntax

    try:
        plain_result = ast.unparse(tree)
        result = black.format_file_contents(
            plain_result, fast=False, mode=black.mode.Mode()
        )
        console = Console()
        syntax = Syntax(result, "python")
        console.print(syntax)  # noqa: T201
    except black.parsing.InvalidInput:
        print(plain_result)  # noqa: T201
    except TypeError:
        pass
