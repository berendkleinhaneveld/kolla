from collections import defaultdict

from .renderer import Renderer


def format_element(element, indent=0):
    if element.type == "TEXT_ELEMENT":
        return f"{'  ' * indent}{element.attributes['text']}"

    result = [f"{'  ' * indent}<{element.type}>"]
    attributes = format_attributes(element.attributes)
    if attributes:
        result[0] = result[0][:-1] + " " + attributes + ">"
    if not element.children:
        result[0] = result[0][:-1] + " />"
    else:
        for child in element.children:
            result.append(format_element(child, indent=indent + 1))
        result.append(f"{'  ' * indent}</{element.type}>")
    return "\n".join(result)


def format_attributes(attributes):
    return " ".join(f'{key}="{val}"' for key, val in attributes.items())


class Element:
    def __init__(self, type):
        self.type = type
        self.children = []
        self.attributes = {}
        self.handlers = defaultdict(set)

    def __repr__(self):
        return format_element(self)


class HTMLRenderer(Renderer):
    """Renderer that renders to a simple Element object that looks a lot like HTML"""

    def create_element(self, type: str) -> dict:
        return Element(type=type)

    def create_text_element(self):
        return Element(type="TEXT_ELEMENT")

    def insert(self, el: Element, parent: Element, anchor=None):
        anchor_idx = parent.children.index(anchor) if anchor else len(parent.children)
        parent.children.insert(anchor_idx, el)

    def remove(self, el: Element, parent: Element):
        parent.children.remove(el)

    def set_element_text(self, el: Element, value: str):
        el.attributes["text"] = value

    def set_attribute(self, el: Element, attr: str, value):
        el.attributes[attr] = value

    def remove_attribute(self, el: Element, attr: str, value):
        if attr in el.attributes:
            del el.attributes[attr]

    def add_event_listener(self, el: Element, event_type, value):
        el.handlers[event_type].add(value)

    def remove_event_listener(self, el: Element, event_type, value):
        el.handlers[event_type].remove(value)
