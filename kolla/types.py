from enum import Enum
from typing import Callable

from observ import watch


class EventLoopType(Enum):
    DEFAULT = "asyncio"
    QT = "Qt"
    SYNC = "sync"


class Select:
    """
    Wrapper around the fragments and expressions that make up a
    v-if/v-else-if/v-else directive block.
    """

    def __init__(self):
        super().__init__()
        self.if_blocks = []
        self.else_fragment: "Fragment" = None
        # TODO: need a way to keep track of which of the expressions
        # to watch. So we'll need the current mounted index or something
        # from the if-blocks.

    def add_if(self, fragment: "Fragment", expression: Callable):
        self.if_blocks.append((fragment, expression))

    def add_else_if(self, fragment: "Fragment", if_block: Callable):
        self.if_blocks.append((fragment, if_block))

    def add_else(self, fragment: "Fragment"):
        self.else_fragment = fragment

    def evaluate(self):
        fragment = None
        for frag, expression in self.if_blocks:
            if expression():
                fragment = frag
                break

        return fragment or self.else_fragment


class Fragment:
    """
    Wrapper fragment around DOM elements which keep track of
    watchers, attributes and directives.
    """

    def __init__(self, tag, parent: "Fragment" = None):
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
        # List of children (Fragment | Select)
        self._children = []
        # Dict of watchers
        self._watchers = {}
        # The DOM element
        self._element = None
        # ...
        self._select_blocks = []

        if parent is not None:
            parent._children.append(self)

    def create(self, renderer):
        # Create the actual DOM element
        self._element = renderer.create_element(self.tag)
        # Set all the static attributes
        for key, value in self._attributes.items():
            renderer.set_attribute(self._element, key, value)
        # Add all event handlers
        for event, handler in self._events.items():
            renderer.add_event_listener(self._element, event, handler)
        # Set all the dynamic attributes
        for key, watcher in self._watchers.items():
            if "bind" in key:
                _, key = key.split(":")
                renderer.set_attribute(self._element, key, watcher.value)
        return self._element

    def set_attribute(self, attr, value):
        self._attributes[attr] = value

    def add_event(self, event, handler):
        self._events[event] = handler

    def add_select_block(self, select):
        self._watchers["bla"] = watch(
            lambda: select.evaluate(),
            deep=True,
            immediate=False,
        )
        self._children.append(select)

    def add_conditional_item(
        # self, name: str, fragment: "Fragment", condition: str, expression, renderer
        self,
        name: str,
        fragment: "Fragment",
        expression,
        renderer,
    ):
        # assert condition in {"v-if", "v-else-if", "v-else"}
        # if condition == "v-if":
        #     self._if_counter += 1

        fragment._visible = expression
        self._watchers[f"v-if:{name}"] = watch(
            fragment._visible, lambda visible: self.insert(renderer, fragment, visible)
        )

    def anchor(self, fragment: "Fragment"):
        found_element = False
        for child in self._children:
            if not found_element:
                if child is fragment:
                    found_element = True
            else:
                if child._visible is None or child._visible():
                    return child

    def mount(self, renderer, target):
        # print("trying to mount:", self.tag, self._attributes)
        # .... TODO: this doesn't work that well...
        visible = self._visible is None or self._visible()
        if visible:
            self.create(renderer)
            renderer.insert(self._element, target)
            for child in self._children:
                if isinstance(child, Select):
                    # NOTE: we can put a watcher on the child.evaluate()!
                    if fragment := child.evaluate():
                        fragment.mount(renderer, target=self._element)
                else:
                    child.mount(renderer, target=self._element)

    def update_select_block(self, select):
        _ = self.anchor(select)

    def insert(self, renderer, fragment: "Fragment", visible: bool):
        # breakpoint()
        if visible:
            fragment.create(renderer)
            anchor = self.anchor(fragment)
            renderer.insert(
                fragment._element, self._element, anchor=anchor and anchor._element
            )
            for child in fragment._children:
                child.mount(renderer, target=fragment._element)
        else:
            renderer.remove(fragment._element, self._element)
            fragment._element = None

    # def ins(self, renderer, fragment, anchor)
