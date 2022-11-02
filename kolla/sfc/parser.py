from __future__ import annotations

import ast
from dataclasses import dataclass, field
from html.parser import HTMLParser

DIRECTIVE_PREFIX = "v-"
DIRECTIVE_BIND = f"{DIRECTIVE_PREFIX}bind"
DIRECTIVE_IF = f"{DIRECTIVE_PREFIX}if"
DIRECTIVE_ELSE_IF = f"{DIRECTIVE_PREFIX}else-if"
DIRECTIVE_ELSE = f"{DIRECTIVE_PREFIX}else"
CONTROL_FLOW_DIRECTIVES = (DIRECTIVE_IF, DIRECTIVE_ELSE_IF, DIRECTIVE_ELSE)
DIRECTIVE_FOR = f"{DIRECTIVE_PREFIX}for"
DIRECTIVE_ON = f"{DIRECTIVE_PREFIX}on"


def parse(source):
    def parse_element(el: Node, parent: Element):
        if el.tag == "script":
            script = ast.parse(el.data, mode="exec")
            return Script(content=script)
        element = Element(el.tag, parent=parent)
        for key, value in el.attrs.items():
            if is_directive(key):
                expr = ast.parse(value, mode="eval")
                value = Expression(content=expr)
            attribute = Attribute(key, value)
            element.attributes.append(attribute)
        for child in el.children:
            element.children.append(parse_element(child, element))
        return element

    parser = TemplateParser()
    parser.feed(source)
    elements = [parse_element(el, parent=None) for el in parser.root.children]
    root = Node("root")
    root.children = elements
    return root


def is_directive(key: str):
    return key.startswith((DIRECTIVE_PREFIX, ":", "@"))


class TemplateParser(HTMLParser):
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


@dataclass
class Expression:
    content: ast.Expression

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
class Script:
    content: ast.Module

    def __repr__(self):
        return "Expression"


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
