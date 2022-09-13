from enum import Enum

from observ import watch


class EventLoopType(Enum):
    DEFAULT = "asyncio"
    QT = "Qt"
    SYNC = "sync"


class Element:
    """Wrapper element around DOM instances which keep track of
    watchers, attributes and directives."""

    def __init__(self, tag, parent: "Element" = None):
        super().__init__()
        # str or function/class of element to create
        self.tag = tag
        # optional: v-if expression to figure out whether to render
        # the element or not
        self._visible = None
        # static attributes for this element
        self._attributes = {}
        # Event listeners
        self._events = {}
        # List of children (Element)
        self._children = []
        # Dict of watchers
        self._watchers = {}
        # The DOM instance
        self._instance = None

        if parent is not None:
            parent._children.append(self)

    def create(self, renderer):
        self._instance = renderer.create_element(self.tag)
        for key, value in self._attributes.items():
            renderer.set_attribute(self._instance, key, value)
        for event, handler in self._events.items():
            renderer.add_event_listener(self._instance, event, handler)
        for key, watcher in self._watchers.items():
            if "bind" in key:
                _, key = key.split(":")
                renderer.set_attribute(self._instance, key, watcher.value)
        return self._instance

    def set_attribute(self, attr, value):
        self._attributes[attr] = value

    def add_event(self, event, handler):
        self._events[event] = handler

    def add_conditional_item(self, name: str, element: "Element", condition, renderer):
        element._visible = condition
        self._watchers[f"v-if:{name}"] = watch(
            element._visible, lambda visible: self.mount(renderer, element, visible)
        )

    def anchor(self, element: "Element"):
        found_element = False
        for child in self._children:
            if not found_element:
                if child is element:
                    found_element = True
            else:
                if child._visible is None or child._visible():
                    return child

    def construct(self, renderer, target):
        visible = self._visible is None or self._visible()
        if visible:
            self.create(renderer)
            renderer.insert(self._instance, target)
            for child in self._children:
                child.construct(renderer, target=self._instance)

    def mount(self, renderer, element: "Element", visible: bool):
        if visible:
            element.create(renderer)
            anchor = self.anchor(element)
            renderer.insert(
                element._instance, self._instance, anchor=anchor and anchor._instance
            )
            for child in element._children:
                child.construct(renderer, target=element._instance)
        else:
            renderer.remove(element._instance, self._instance)
            element._instance = None
