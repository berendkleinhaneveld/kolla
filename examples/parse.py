from __future__ import annotations

import ast
import textwrap
from dataclasses import dataclass, field
from html.parser import HTMLParser

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
    type: str = "Element"

    def __repr__(self):
        attributes = " ".join(str(attr) for attr in self.attributes).strip()
        children = "\n".join(str(child) for child in self.children).strip()
        return f"<{self.name} {attributes}>\n{children}\n</{self.name}>"


def parse(source):
    def parse_element(el: Node):
        if el.tag == "script":
            script = ast.parse(el.data, mode="exec")
            return Script(content=script)
        element = Element(el.tag)
        for key, value in el.attrs.items():
            if key.startswith((":", "@", "v-")):
                expr = ast.parse(value, mode="eval")
                value = Expression(content=expr)
            attribute = Attribute(key, value)
            element.attributes.append(attribute)
        for child in el.children:
            element.children.append(parse_element(child))
        return element

    parser = KollaParser()
    parser.feed(source)
    elements = [parse_element(el) for el in parser.root.children]
    root = Node("root")
    root.children = elements
    return root


def traverse(tree, result):
    if hasattr(tree, "children"):
        for child in tree.children:
            traverse(child, result)
    if hasattr(tree, "attributes"):
        for attr in tree.attributes:
            traverse(attr, result)

    # breakpoint()
    if isinstance(tree, Element):
        for attr in tree.attributes:
            if isinstance(attr.value, Expression):
                scope_info = ast_scope.annotate(attr.value.content)
                print(f"add: {scope_info.global_scope.symbols_in_frame}")
                result["will_use_in_template"].update(
                    scope_info.global_scope.symbols_in_frame
                )


class NodeTraverser(ast.NodeVisitor):
    def __init__(self, scope_info):
        super().__init__()
        self.scope_info = scope_info
        self.result = set()
        self.depth = 0

    def generic_visit(self, node):
        # Increase scope depth when entering functions
        if isinstance(node, ast.FunctionDef):
            self.depth += 1

        if self.depth > 0 and hasattr(node, "ctx"):
            if isinstance(node.ctx, ast.Store):
                # Variables have to be marked 'global'
                if self.scope_info[node] == self.scope_info.global_scope:
                    self.result.add(node.id)

        super().generic_visit(node)

        if isinstance(node, ast.FunctionDef):
            self.depth -= 1


def analyse(tree):
    script = [element for element in tree.children if isinstance(element, Script)][0]
    assert script

    scope_info = ast_scope.annotate(script.content)

    variables = scope_info.global_scope.symbols_in_frame

    trav = NodeTraverser(scope_info)
    trav.visit(script.content)

    result = {
        "variables": variables,
        "will_change": trav.result,
        "will_use_in_template": set(),
    }
    traverse(tree, result)
    return result


def generate(tree, analysis):
    pass


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
    print(analysis)

    code = generate(tree, analysis)
