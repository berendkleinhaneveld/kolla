from __future__ import annotations
from typing import Any, Callable
from weakref import ref

from observ.watcher import watch, Watcher  # type: ignore

from kolla.renderers import Renderer


# "Fragment" = TypeVar(""Fragment"")


class Fragment:
    def __init__(
        self,
        renderer: Renderer,
        # tag = None for 'transient' Fragments, like a virtual root
        tag: None | str | Callable | list[str | Callable] = None,
        parent: "Fragment" | None = None,
    ):
        super().__init__()

        self.renderer = renderer
        self.tags: list[str | Callable] = []
        self.elements: list[Any] = []
        self.children: list["Fragment"] = []

        self._parent: ref["Fragment"] | None = ref(parent) if parent else None
        self._attributes: dict[str, str] = {}
        self._events: dict[str, Callable] = {}

        if isinstance(tag, str):
            self.tags = [tag]

        self._watchers: dict[str, Watcher] = {}

        if parent:
            parent.children.append(self)

    @property
    def parent(self) -> "Fragment" | None:
        return self._parent() if self._parent else None

    @parent.setter
    def parent(self, parent: "Fragment"):
        self._parent = ref(parent)

    @property
    def first(self) -> Any | None:
        return self.elements and self.elements[0]

    def set_attribute(self, attr, value):
        self._attributes[attr] = value

    def set_bind(self, attr, expression):
        self._watchers[f"bind:{attr}"] = watch(
            expression,
            lambda new: self.renderer.set_attribute(self.first, attr, new),
            immediate=False,
        )

    def add_event(self, event, handler):
        self._events[event] = handler

    def create(self):
        """
        Creates instance, depending on whether there is
        an expression
        """
        for tag in self.tags:
            # Create the element
            element = self.renderer.create_element(tag)
            self.elements.append(element)
            # Set all static attributes
            for attr, value in self._attributes.items():
                self.renderer.set_attribute(element, attr, value)
            # Add all event handlers
            # TODO: check what happens within v-for constructs?
            for event, handler in self._events.items():
                self.renderer.add_event_listener(element, event, handler)
            # Set all dynamic aatributes
            for key, watcher in self._watchers.items():
                if key.startswith("bind:"):
                    _, key = key.split(":")
                    self.renderer.set_attribute(element, key, watcher.value)
        # IDEA/TODO: for v-for, don't create instances direct, but
        # instead, create child fragments first, then call
        # create on those instead. Might involve some reparenting
        # of the current child fragments???

    def mount(self, target: Any, anchor: Any | None = None):
        self.create()
        for element in self.elements:
            self.renderer.insert(element, parent=target, anchor=anchor)
            for child in self.children:
                child.mount(element)

    def unmount(self):
        pass

    def patch(self):
        pass

    def anchor(self, other: "Fragment") -> "Fragment":
        """Returns the fragment that serves as anchor for the
        other fragment. Anchor is the first mounted item *after* the
        current item.
        """
        pass
