from __future__ import annotations

from enum import Enum
from itertools import zip_longest
from typing import Any, Callable
from weakref import ref

from observ import reactive
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
        self._props: dict[str, Any] | None = None

        if parent:
            parent.children.append(self)

    def __repr__(self):
        return f"<{type(self).__name__}({self.tag})>"

    @property
    def parent(self) -> "Fragment" | None:
        return self._parent() if self._parent else None

    @parent.setter
    def parent(self, parent: "Fragment"):
        self._parent = ref(parent)

    def set_attribute(self, attr, value):
        """
        Set a static attribute. Will only be applied to element on `create`.
        """
        self._attributes[attr] = value

    def set_bind(self, attr, expression, immediate=False):
        """
        Set a dynamic attribute to the value of the expression. This will
        only be applied on `create`
        """

        def update(new):
            if self.element:
                self.renderer.set_attribute(self.element, attr, new)
            elif self._props:
                self._props[attr] = new

        self._watchers[f"bind:{attr}"] = watch(
            expression,
            update,
            immediate=immediate,
        )

    def set_bind_dict(self, name, expression):
        """
        Set dynamic attributes for all of the keys in the value of the expression.

        The dict of the expression will be watched for the keys. For each new key,
        `set_bind` is called to create a dynamic attribute for the value of that
        key. When a key is removed, then the specific watcher is removed and some
        cleanup performed.
        """

        def update(new, old):
            for attr in new - (old or set()):
                self.set_bind(
                    attr,
                    lambda: expression()[attr],
                    immediate=bool(self.element or self._props),
                )

            for attr in (old or set()) - new:
                del self._watchers[f"bind:{attr}"]
                # Perform cleanup
                if self.element:
                    self.renderer.remove_attribute(self.element, attr, None)
                elif self._props:
                    del self._props[attr]

        self._watchers[f"bind_dict:{name}"] = watch(
            lambda: set(expression().keys()),
            update,
            immediate=True,
            deep=True,
        )

    def set_type(self, expression):
        def update_type(tag):
            self.unmount()
            self.tag = tag
            # TODO: also figure out the right anchor
            # Maybe ask parent for the right anchor?
            self.mount(self.target)

        # Update the tag immediately
        self.tag = expression()
        self._watchers["type"] = watch(
            expression,
            update_type,
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
        if self.tag == "template":
            return

        # Create the element
        self.element = self.renderer.create_element(self.tag)
        # Set all static attributes
        for attr, value in self._attributes.items():
            self.renderer.set_attribute(self.element, attr, value)
        self._attributes.clear()

        # Add all event handlers
        # TODO: check what happens within v-for constructs?
        for event, handler in self._events.items():
            self.renderer.add_event_listener(self.element, event, handler)
        # Set all dynamic attributes
        for key, watcher in self._watchers.items():
            if key.startswith("bind:"):
                _, attr = key.split(":")
                self.renderer.set_attribute(self.element, attr, watcher.value)
        # IDEA/TODO: for v-for, don't create instances direct, but
        # instead, create child fragments first, then call
        # create on those instead. Might involve some reparenting
        # of the current child fragments???

    def mount(self, target: Any, anchor: Any | None = None):
        self.target = target
        self.create()

        if self.element:
            self.renderer.insert(self.element, parent=target, anchor=anchor)
        for child in self.children:
            child.mount(self.element or target)

    def unmount(self):
        for child in self.children:
            child.unmount()

        if self.element:
            self.renderer.remove(self.element, self.target)
            self.element = None
        elif self._props:
            self._props = None

    def first(self):
        """
        Returns the first DOM element (if any), from either itself, or its decendants,
        in case of virtual fragments.
        """
        if self.element:
            return self.element
        for child in self.children:
            if child.element:
                return child.element

    def patch(self, context):
        pass

    def anchor(self, other: "Fragment") -> "Fragment":
        """
        Returns the fragment that serves as anchor for the
        other fragment. Anchor is the first mounted item *after* the
        current item.
        """
        if self.children:
            idx = self.children.index(other)
            length = len(self.children) - 1
            while idx < length:
                idx += 1
                if element := self.children[idx].first():
                    return element


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
                if self.parent:
                    anchor = self.parent.anchor(self)
                new.mount(self.target, anchor)

        self._watchers["control_flow"] = watch(
            active_child,
            update_fragment,
            deep=True,
            immediate=True,
        )


class ListFragment(Fragment):
    """
    1. Handle expression (for 'X' in 'Y') in multiple parts (by analyzing the
       AST):
        A. Create a watcher for collection 'Y'
        B. Callback will create (or update existing) Fragments
            - When unkeyed:
                idx = 0
                for 'X' in 'Y':
                    if idx < len(fragments):
                        fragment = fragments[idx]
                    else:
                        fragment = Fragment(...)
                    ...
                    idx += 1
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **{**kwargs, "type": FragmentType.LIST})
        self.create_fragment: Callable | None = None
        self.expression: str = None
        # NOTE: use expression attribute

    def set_create_fragment(self, create_fragment: Callable, is_keyed: bool):
        self.create_fragment = create_fragment
        self.is_keyed = is_keyed

    def set_expression(self, expression: str):
        self.expression = expression

    def mount(self, target: Any, anchor: Any | None = None):
        self.target = target

        def update_list(items):
            # TODO: adjust method based on keyed/unkeyed
            if self.children:
                for child, item in zip_longest(self.children, items):
                    if child and item:
                        # TODO: generate patch closures for each fragment
                        #       in the sfc
                        child.patch(item)
                    elif child:
                        # item is None
                        child.unmount()
                    elif item:
                        # child is None:
                        fragment = self.create_fragment(item)
                        self.children.append(fragment)
                        fragment.parent = self
                        fragment.mount(target)
            else:
                for context in items:
                    fragment = self.create_fragment(context)
                    self.children.append(fragment)
                    fragment.parent = self

                for child in self.children:
                    child.mount(target)

        self._watchers["list"] = watch(
            self.expression,
            update_list,
            immediate=True,
            deep=True,
        )


class ComponentFragment(Fragment):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **{**kwargs, "type": FragmentType.COMPONENT})
        self.component = None
        self.fragment = None

    def create(self):
        if self.tag is None:
            return

        self._props = reactive({})
        # Set static attributes
        self._props.update(self._attributes)

        # Set dynamic attributes
        for key, watcher in self._watchers.items():
            if key.startswith("bind:"):
                _, attr = key.split(":")
                self._props[attr] = watcher.value

        self.component = self.tag(self._props)
        self.fragment = self.component.render(self.renderer)

        # Add all event handlers
        for event, handler in self._events.items():
            self.component.add_event_handler(event, handler)

    def mount(self, target: Any, anchor: Any | None = None):
        self.target = target
        self.create()

        if self.fragment:
            self.fragment.mount(target)
        else:
            for child in self.children:
                child.mount(self.element or target)
