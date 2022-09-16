from typing import Any, Callable, TypeVar
from weakref import ref

from observ.watcher import watch, Watcher  # type: ignore

from kolla.renderers import Renderer


Frag = TypeVar("Fragment")


class Fragment:
    def __init__(
        self,
        renderer: Renderer,
        # tag = None for 'transient' Fragments, like a virtual root
        tag: None | str | Callable | list[str | Callable] = None,
        parent: Frag | None = None,
    ):
        super().__init__()

        self.renderer = renderer
        self.tags: list[str | Callable] = []
        self.elements: list[Any] = []
        self._parent: ref[Frag] | None = parent
        self._attributes = {}

        if isinstance(tag, str):
            self.tags = [tag]

        self.children: list[Frag] = []
        self._watchers: dict[str, Watcher] = {}

        if parent:
            parent.children.append(self)
        # create_instane
        # static_instance: Any  # (no expression)
        # dynamic_instance: Any  # (depends on expression)
        # - works for 'select' block
        # - works for dynamic type block

    @property
    def parent(self) -> Frag | None:
        if self._parent:
            return self._parent()
        return None
        # return self._parent and self._parent()

    @parent.setter
    def parent(self, parent: Frag):
        self._parent = ref(parent)

    @property
    def first(self) -> Any | None:
        return self.elements and self.elements[0]

    def set_attribute(self, attr, value):
        self._attributes[attr] = value

    def set_dynamic_attribute(self, attr, expression):
        self._watchers[f"bind:{attr}"] = watch(
            expression,
            lambda new: self.renderer.set_attribute(self.first, attr, new),
            immediate=False,
        )

    def create(self):
        """
        Creates instance, depending on whether there is
        an expression
        """
        for tag in self.tags:
            element = self.renderer.create_element(tag)
            self.elements.append(element)
            for attr, value in self._attributes.items():
                self.renderer.set_attribute(element, attr, value)

            for key, watcher in self._watchers.items():
                if key.startswith("bind:"):
                    watcher.update()
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

    def anchor(self, other: Frag) -> Frag:
        """Returns the fragment that serves as anchor for the
        other fragment. Anchor is the first mounted item *after* the
        current item.
        """
        pass


class StaticFragment:
    tag: str


class SelectFragment:
    if_statements: list
    else_statement: list | None


class DynamicFragment:
    pass


class EachFragment:
    pass
