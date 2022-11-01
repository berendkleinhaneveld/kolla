from __future__ import annotations

import ast
import textwrap
from collections import defaultdict
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

import ast_scope
from rich import print

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
            if value is None:
                node.attrs[key] = True

        # Add item as child to the last on the stack
        self.stack[-1].children.append(node)
        # Make the new node the last on the stack
        self.stack.append(node)

    def handle_endtag(self, tag):
        # Pop the stack
        node = self.stack.pop()
        assert tag == node.tag
        node.end = self.getpos()

    def handle_data(self, data):
        if data := data.strip():
            self.stack[-1].data = data


@dataclass
class Expression:
    content: ast.Expression

    def __repr__(self):
        return "Expression"


@dataclass
class Script:
    content: ast.Module

    def __repr__(self):
        return "Expression"


@dataclass
class Attribute:
    name: str
    value: str | Expression
    type: str = "Attribute"

    def __hash__(self):
        return id(self)

    def __repr__(self):
        return f"{self.name}={self.value}"


@dataclass
class Text:
    content: str
    type: str = "Text"
    children: [Expression] = field(default_factory=list)  # TODO


@dataclass
class Element:
    name: str
    attributes: [Attribute] = field(default_factory=list)
    children: ["Element" | Text] = field(default_factory=list)
    parent: "Element" = None
    type: str = "Element"

    def __hash__(self):
        return id(self)

    def __repr__(self):
        attributes = " ".join(str(attr) for attr in self.attributes).strip()
        children = "\n".join(str(child) for child in self.children).strip()
        return f"<{self.name} {attributes}>\n{children}\n</{self.name}>"


def parse(source):
    def parse_element(el: Node, parent: Element):
        if el.tag == "script":
            script = ast.parse(el.data, mode="exec")
            return Script(content=script)
        element = Element(el.tag, parent=parent)
        for key, value in el.attrs.items():
            if key.startswith((":", "@", "v-")):
                expr = ast.parse(value, mode="eval")
                value = Expression(content=expr)
            attribute = Attribute(key, value)
            element.attributes.append(attribute)
        for child in el.children:
            element.children.append(parse_element(child, element))
        return element

    parser = KollaParser()
    parser.feed(source)
    elements = [parse_element(el, parent=None) for el in parser.root.children]
    root = Node("root")
    root.children = elements
    return root


def traverse(element, result):
    if hasattr(element, "children"):
        for child in element.children:
            traverse(child, result)
    if hasattr(element, "attributes"):
        for attr in element.attributes:
            traverse(attr, result)

    if isinstance(element, Element):
        for attr in element.attributes:
            if isinstance(attr.value, Expression):
                scope_info = ast_scope.annotate(attr.value.content)
                result["will_use_in_template"].update(
                    scope_info.global_scope.symbols_in_frame
                )
                if changes := scope_info.global_scope.symbols_in_frame & set(
                    result["will_change"]
                ):
                    for change in changes:
                        result["will_change_elements"][change].add((element, attr))


class DependencyFinder(ast.NodeVisitor):
    def __init__(self, scope_info):
        super().__init__()
        self.scope_info = scope_info
        self.result = defaultdict(set)
        self.depth = 0

    def generic_visit(self, node):
        # Increase scope depth when entering functions
        if isinstance(node, ast.FunctionDef):
            self.depth += 1

        if self.depth > 0 and hasattr(node, "ctx"):
            if isinstance(node.ctx, ast.Store):
                # Variables have to be marked 'global'
                if self.scope_info[node] == self.scope_info.global_scope:
                    # TODO: maybe add the node itself instead of just id?
                    self.result[node.id].add(node)

        super().generic_visit(node)

        if isinstance(node, ast.FunctionDef):
            self.depth -= 1


def analyse(tree):
    script = [element for element in tree.children if isinstance(element, Script)][0]
    assert script

    scope_info = ast_scope.annotate(script.content)

    variables = scope_info.global_scope.symbols_in_frame

    dep_finder = DependencyFinder(scope_info)
    dep_finder.visit(script.content)

    result = {
        # TODO: instead of just the name, store a set of expressions keyed on used
        # variable name?
        "variables": variables,
        "will_change": dep_finder.result,
        "will_use_in_template": set(),
        "will_change_elements": defaultdict(set),
    }
    traverse(tree, result)
    return result


def ast_set_attributes(el: str, element: Element, analysis):
    result = []

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

    return result


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


def ast_add_event_listener(el: str, key: str, value, symbols: set):
    split_char = "@" if key.startswith("@") else ":"
    _, key = key.split(split_char)

    expression_ast = value.content
    # expression_ast = ast.parse(value, mode="eval")

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


counter = defaultdict(int)


def numbered_tag(tag):
    count = counter[tag]
    counter[tag] += 1
    return f"{tag}_{count}"


def ast_create_fragment_function(tree, analysis):
    elements = {}

    def gather_tags(element):
        if isinstance(element, Element):
            elements[numbered_tag(element.name)] = element

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

    element_creations = [
        ast.Assign(
            targets=[ast.Name(id=el, ctx=ast.Store())],
            value=ast.Call(
                func=ast.Attribute(
                    value=ast.Name(id="renderer", ctx=ast.Load()),
                    attr="create_element",
                    ctx=ast.Load(),
                ),
                args=[ast.Constant(value=element.name)],
                keywords=[],
            ),
        )
        for el, element in elements.items()
    ]
    element_set_attributes = []
    for el, element in elements.items():
        element_set_attributes.extend(ast_set_attributes(el, element, analysis))

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
        # TODO: Need to loop over the expressions which contain any of the names
        for element, attr in analysis["will_change_elements"][name]:
            print(attr)
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
                    ast.Nonlocal(names=list(elements)),
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
                # TODO: implement update logic
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
                    # *ast_remove_event_listeners(attributes),
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
        self.nodes = []

    def generic_visit(self, node):
        if isinstance(node, ast.FunctionDef):
            self.depth += 1

        if (
            self.depth > 0
            and hasattr(node, "ctx")
            and isinstance(node.ctx, ast.Store)
            and self.scope_info[node] == self.scope_info.global_scope
        ):
            self.nodes.append(node)

        super().generic_visit(node)

        if isinstance(node, ast.FunctionDef):
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


def ast_instance_function(script_tree, analysis):
    scope_info = ast_scope.annotate(script_tree)

    # FIXME: the NodeInvalidatorFinder can be replaced if the analysis is a bit smarter
    # First traverse the tree to find the assignment nodes
    # Then traverse again to find the parents of those nodes and
    # insert the invalidate call right after the assignment calls
    invalidator_finder = NodeInvalidatorFinder(scope_info)
    invalidator_finder.visit(script_tree)

    invalidator_wrapper = NodeInvalidatorWrapper(invalidator_finder.nodes)
    invalidator_wrapper.visit(script_tree)

    symbols = [
        ast.Constant(value=symbol) for symbol in analysis["will_use_in_template"]
    ]

    symbol_refs = [ast.Name(id=name.value, ctx=ast.Load()) for name in symbols]

    # This is needed to update the
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


def ast_create_component_class(filename):
    file_name = Path(filename).stem
    file_name_parts = [part.capitalize() for part in file_name.split("_")]
    class_name = "".join(file_name_parts)
    # def __init__(self, options):
    #     super().__init__()
    #     self.init(options, instance, create_fragment)
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


def generate(tree, analysis):
    # Process tree
    # TODO: create fragments n stuff
    fragment_function = ast_create_fragment_function(tree, analysis)

    # Keep lists of code that is about to be generated
    # generated = {
    #     "variables": [],
    #     "create": [],
    #     "mount": [],
    #     "update": [],
    #     "unmount": [],
    # }

    # Create component class
    class_name, class_tree = ast_create_component_class(__file__)

    # Create instance function from the script tag
    script = [element for element in tree.children if isinstance(element, Script)][0]
    instance_function, symbols = ast_instance_function(script.content, analysis)

    # Rewrite the script as 'instance' method
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
            fragment_function,
            instance_function,
            class_tree,
            # TODO: insert if __name__ == "__main__": part to make file runnable?
        ],
        type_ignores=[],
    )
    return module


def pretty_code_print(tree, out=None):
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

    if out:
        with open(out, mode="w", encoding="utf-8") as fh:
            fh.write(result)


if __name__ == "__main__":
    source = textwrap.dedent(
        """
        <widget>
          <label :text="count" />
          <button text="Bump" @clicked="bump" />
        </widget>

        <script>
        from PySide6 import QtWidgets
        count = 0

        def bump():
            global count
            count += 1
        </script>
        """
    )

    tree = parse(source)

    analysis = analyse(tree)

    generated_code = generate(tree, analysis)

    ast.fix_missing_locations(generated_code)

    pretty_code_print(generated_code, "parse_example.py")

    # print(ast.dump(generated_code, indent=2))
    # with open("parse_example.py", mode="r") as fh:
    #     content = fh.read()

    # blackened = ast.parse(content, mode="exec")
    # print(ast.dump(blackened, indent=2))
    # exit()

    # Compile the tree into a code object (module)
    code = compile(generated_code, filename="none", mode="exec")
    # Execute the code as module and pass a dictionary that will capture
    # the global and local scope of the module
    module_namespace = {}
    exec(code, module_namespace)

    # Check that the class definition is an actual subclass of Component
    component_class = module_namespace["Parse"]

    target = {}
    options = {"target": target}

    component_instance = component_class(options)
    print(component_instance)
    # print(target)
    button = target["children"][0]["children"][1]
    print(button)

    for handler in button["handlers"]["clicked"]:
        print("CLICK!")
        handler()

    from kolla.component import scheduler

    scheduler.flush()

    print(target)
