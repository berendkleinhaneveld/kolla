import ast
from collections import defaultdict
import logging

# import inspect
from html.parser import HTMLParser
from pathlib import Path
import re
import sys
import textwrap

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
    Load template from a string
    """
    if path is None:
        path = "<template>"

    # Construct the AST tree
    tree, name = construct_ast(path=path, template=template)

    # breakpoint()

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
    render_tree = create_kolla_render_function(parser.root, names=imported_names.names)
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


def ast_create_fragment(el, tag, parent=None):
    """
    Return AST for creating an element with `tag` and
    assigning it to variable name: `el`
    """
    keywords = [
        ast.keyword(arg="tag", value=ast.Constant(value=tag)),
    ]
    if parent is not None:
        keywords.append(
            ast.keyword(arg="parent", value=ast.Name(id=parent, ctx=ast.Load()))
        )
    return ast.Assign(
        targets=[ast.Name(id=el, ctx=ast.Store())],
        value=ast.Call(
            func=ast.Name(id="Fragment", ctx=ast.Load()),
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


def ast_set_dynamic_attribute(el, key, value):
    _, key = key.split(":")
    source = ast.parse(
        textwrap.dedent(
            f"""
            {el}.set_dynamic_attribute("{key}", lambda: {value})
            #{el}._watchers["bind:{key}"] = watch(
            #    lambda: {value},
            #    lambda new: renderer.set_attribute({el}._instance, "{key}", new),
            #)
            """
        ),
        mode="exec",
    )
    lambda_names = LambdaNamesCollector()
    lambda_names.visit(source)
    return (
        RewriteName(skip={"renderer", "new", el, "watch"} | lambda_names.names)
        .visit(source)
        .body
    )


def ast_add_event_listener(el, key, value):
    split_char = "@" if key.startswith("@") else ":"
    _, key = key.split(split_char)

    expression_ast = ast.parse(value, mode="eval")
    # v-on directives allow for lambdas which define arguments
    # which need to be skipped by the RewriteName visitor
    lambda_names = LambdaNamesCollector()
    lambda_names.visit(expression_ast)
    RewriteName(skip=set() | lambda_names.names).visit(expression_ast)

    return ast.Expr(
        value=ast.Call(
            func=ast.Attribute(
                value=ast.Name(id=el, ctx=ast.Load()),
                attr="add_event",
                ctx=ast.Load(),
            ),
            args=[
                ast.Constant(value=key),
                expression_ast.body,
            ],
            keywords=[],
        )
    )


def ast_add_condictional(parent, child, condition):
    condition_ast = ast.parse(f"lambda: bool({condition})", mode="eval")
    RewriteName(skip=set()).visit(condition_ast)

    return ast.Expr(
        value=ast.Call(
            func=ast.Attribute(
                value=ast.Name(id=parent, ctx=ast.Load()),
                attr="add_conditional_item",
                ctx=ast.Load(),
            ),
            args=[
                ast.Constant(value=child),
                ast.Name(id=child, ctx=ast.Load()),
                condition_ast.body,
                ast.Name(id="renderer", ctx=ast.Load()),
            ],
            keywords=[],
        )
    )


def create_kolla_render_function(node, names):
    body = []
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
            names=[ast.alias(name="Fragment")],
            level=0,
        )
    )
    body.append(
        ast.Assign(
            targets=[ast.Name(id="elements", ctx=ast.Store())],
            value=ast.List(elts=[], ctx=ast.Load()),
        )
    )

    counter = defaultdict(int)
    for child in node.children:
        # Create element name
        el = f"{child.tag}{counter[child.tag]}"
        # el = f"el{counter}"
        counter[child.tag] += 1
        # Create element
        body.append(ast_create_fragment(el, child.tag))
        # Set static attributes
        for key, value in child.attrs.items():
            if not is_directive(key):
                body.append(ast_set_attribute(el, key, value))
            elif key.startswith((DIRECTIVE_BIND, ":")):
                if key == DIRECTIVE_BIND:
                    # TODO: bind complete dicts
                    pass
                else:
                    body.extend(ast_set_dynamic_attribute(el, key, value))
            elif key.startswith((DIRECTIVE_ON, "@")):
                body.append(ast_add_event_listener(el, key, value))
            # TODO: how to support root-level v-ifs??
            # Maybe just not support it for now?
            # elif key.startswith(DIRECTIVE_IF):
            #     body.append(ast_add_condictional(target, el, value))

        # Create and add children
        def create_children(nodes, target):
            result = []
            for child in nodes:
                nonlocal counter
                # Create element name
                el = f"{child.tag}{counter[child.tag]}"
                # el = f"el{counter}"
                counter[child.tag] += 1
                # Create element
                result.append(ast_create_fragment(el, child.tag, parent=target))
                # Set static attributes and dynamic (bind) attributes
                for key, value in child.attrs.items():
                    if not is_directive(key):
                        result.append(ast_set_attribute(el, key, value))
                    elif key.startswith((DIRECTIVE_BIND, ":")):
                        if key == DIRECTIVE_BIND:
                            # TODO: bind complete dicts
                            pass
                        else:
                            result.extend(ast_set_dynamic_attribute(el, key, value))
                    elif key.startswith((DIRECTIVE_ON, "@")):
                        result.append(ast_add_event_listener(el, key, value))
                    elif key.startswith(DIRECTIVE_IF):
                        result.append(ast_add_condictional(target, el, value))

                # Mount new element in hierarchy
                # result.append(ast_insert_element(el, target))

                # Process the children
                result.extend(create_children(child.children, el))

            return result

        body.extend(create_children(child.children, el))

        # Append el to elements
        body.append(
            ast.Expr(
                value=ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(id="elements", ctx=ast.Load()),
                        attr="append",
                        ctx=ast.Load(),
                    ),
                    args=[ast.Name(id=el, ctx=ast.Load())],
                    keywords=[],
                )
            ),
        )

    body.append(ast.Return(value=ast.Name(id="elements", ctx=ast.Load())))

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
    except TypeError:
        pass
