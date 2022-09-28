from __future__ import annotations
from enum import Enum
from typing import Any, Callable
from weakref import ref

from observ.watcher import watch, Watcher  # type: ignore

from kolla.renderers import Renderer


class FragmentType(Enum):
    NORMAL = 0
    CONTROL_FLOW = 1
    LIST = 2
    COMPONENT = 3


class Fragment:
    def __init__(
        self,
        renderer: Renderer,
        # tag = None for 'transient' Fragments, like a virtual root
        tag: None | str | Callable = None,
        parent: "Fragment" | None = None,
        type: FragmentType = FragmentType.NORMAL,
    ):
        super().__init__()

        self.renderer = renderer
        self.tag: str | Callable = tag
        self.element: Any = None
        self.children: list["Fragment"] = []
        self.target = None

        self._parent: ref["Fragment"] | None = ref(parent) if parent else None
        self._attributes: dict[str, str] = {}
        self._events: dict[str, Callable] = {}
        self._watchers: dict[str, Watcher] = {}

        if parent:
            parent.children.append(self)

    def __repr__(self):
        return f"<Fragment({self.tag})>"

    @property
    def parent(self) -> "Fragment" | None:
        return self._parent() if self._parent else None

    @parent.setter
    def parent(self, parent: "Fragment"):
        self._parent = ref(parent)

    def set_attribute(self, attr, value):
        self._attributes[attr] = value

    def set_bind(self, attr, expression):
        self._watchers[f"bind:{attr}"] = watch(
            expression,
            lambda new: self.renderer.set_attribute(self.element, attr, new),
            immediate=False,
        )

    def set_condition(self, expression):
        self.condition = expression

    def add_event(self, event, handler):
        self._events[event] = handler

    def create(self):
        """
        Creates instance, depending on whether there is
        an expression
        """

        # Create the element
        self.element = self.renderer.create_element(self.tag)
        # Set all static attributes
        for attr, value in self._attributes.items():
            self.renderer.set_attribute(self.element, attr, value)
        # Add all event handlers
        # TODO: check what happens within v-for constructs?
        for event, handler in self._events.items():
            self.renderer.add_event_listener(self.element, event, handler)
        # Set all dynamic aatributes
        for key, watcher in self._watchers.items():
            if key.startswith("bind:"):
                _, key = key.split(":")
                self.renderer.set_attribute(self.element, key, watcher.value)
        # IDEA/TODO: for v-for, don't create instances direct, but
        # instead, create child fragments first, then call
        # create on those instead. Might involve some reparenting
        # of the current child fragments???

    def mount(self, target: Any, anchor: Any | None = None):
        self.target = target
        self.create()
        self.renderer.insert(self.element, parent=target, anchor=anchor)
        for child in self.children:
            child.mount(self.element)

    def unmount(self):
        for child in self.children:
            child.unmount()

        self.renderer.remove(self.element, self.target)
        self.element = None

    def patch(self):
        pass

    def anchor(self, other: "Fragment") -> "Fragment":
        """Returns the fragment that serves as anchor for the
        other fragment. Anchor is the first mounted item *after* the
        current item.
        """
        pass


class ControlFlowFragment(Fragment):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **{**kwargs, "type": FragmentType.CONTROL_FLOW})

    def mount(self, target: Any, anchor: Any | None = None):
        self.target = target

        def active_child():
            for child in self.children:
                if hasattr(child, "condition"):
                    if child.condition():
                        return child
                else:
                    return child

        def update_fragment(new, old):
            if old:
                old.unmount()
            if new:
                new.mount(self.target)

        self._watchers["control_flow"] = watch(
            active_child,
            update_fragment,
            deep=True,
            immediate=True,
        )


class ListFragment(Fragment):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **{**kwargs, "type": FragmentType.LIST})


class ComponentFragment(Fragment):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **{**kwargs, "type": FragmentType.COMPONENT})

    def mount(self, target: Any, anchor: Any | None = None):
        self.target = target
        # Virtual node, so mount children into target
        for child in self.children:
            child.mount(target)
