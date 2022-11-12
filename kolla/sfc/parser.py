from __future__ import annotations

import ast
from collections import defaultdict
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
    counter = defaultdict(int)

    def numbered_tag(tag):
        tag = tag.replace("-", "_").lower()
        count = counter[tag]
        counter[tag] += 1

        return f"{tag}_{count}"

    def parse_element(node: Node, parent: Element):
        if node.tag == "script":
            script = ast.parse(node.data, mode="exec")
            return Script(content=script)
        element = Element(node.tag, parent=parent)
        element.name = numbered_tag(element.tag)
        for key, value in node.attrs.items():
            if is_directive(key):
                expr = ast.parse(value, mode="eval")
                value = Expression(content=expr, raw=value)
            attribute = Attribute(key, value)
            element.attributes.append(attribute)
        if node.data:
            text = Text(content=node.data, parent=element)
            text.name = numbered_tag("text")
            element.children.append(text)
        for child in node.children:
            element.children.append(parse_element(child, element))
        return element

    parser = TemplateParser()
    parser.feed(source)
    elements = [parse_element(node, parent=None) for node in parser.root.children]
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
    raw: str


@dataclass
class Attribute:
    name: str
    value: str | Expression

    @property
    def is_dynamic(self):
        return self.name.startswith((DIRECTIVE_BIND, ":"))

    @property
    def key(self):
        if self.name.startswith((DIRECTIVE_BIND, ":")):
            _, key = self.name.split(":")
            return key
        return self.name

    def __hash__(self):
        return id(self)


@dataclass
class Script:
    content: ast.Module


@dataclass
class Text:
    content: str
    parent: "Element" = None
    children: [Expression] = field(default_factory=list)  # TODO

    @property
    def is_component(self):
        return False


@dataclass
class Element:
    # Tag from the template, in original casing
    tag: str
    attributes: [Attribute] = field(default_factory=list)
    children: ["Element" | Text] = field(default_factory=list)
    parent: "Element" = None
    # Variable name (numbered)
    name: str = None

    @property
    def is_component(self):
        return self.tag[0].isupper()

    def __hash__(self):
        return id(self)
