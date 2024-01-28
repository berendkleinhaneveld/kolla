from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar
from weakref import ref

from observ import computed, reactive
from observ.proxy import Proxy
from observ.watcher import Watcher, watch  # type: ignore

from .component import Component
from .renderers import Renderer
from .weak import weak

DomElement = TypeVar("DomElement")


class Fragment:
    def __init__(
        self,
        renderer: Renderer,
        # tag = None for 'transient' Fragments, like a virtual root
        tag: str | Callable[[], Component] | None = None,
        parent: Fragment | None = None,
    ):
        super().__init__()

        # The tag for the fragment
        self.tag: str | Callable = tag
        # Reference to the renderer
        # TODO: don't pass the renderer to the fragments...
        self.renderer = renderer
        # List of child fragments
        self.children: list[Fragment] = []
        # Dom element (if any)
        self.element: DomElement = None
        # Target dom-element to render in
        self.target: DomElement = None

        # Weak ref to parent fragment
        self._parent: ref[Fragment] | None = ref(parent) if parent else None
        self._attributes: dict[str, str] = {}
        self._events: dict[str, Callable] = {}
        self._watchers: dict[str, Watcher] = {}
        self.props: dict[str, Any] | None = None

        self.condition: Callable | None = None

        # TODO: maybe this next line is a bit nasty, but
        # on the other hand, it makes sure that the
        # relationship between this item and its parent
        # is set correctly
        if parent:
            parent.children.append(self)

    def __repr__(self):
        return f"<{type(self).__name__}({self.tag})>"

    @property
    def parent(self) -> Fragment | None:
        return self._parent() if self._parent else None

    @parent.setter
    def parent(self, parent: Fragment):
        # TODO: should this also check that this item is
        # now in the list of the parent's children?
        self._parent = ref(parent)

    def first(self) -> DomElement | None:
        """
        Returns the first DOM element (if any), from either itself, or its decendants,
        in case of virtual fragments.
        """
        if self.element:
            return self.element
        for child in self.children:
            if child.element:
                return child.element

    def anchor(self, other: Fragment) -> DomElement | None:
        """
        Returns the fragment that serves as anchor for the given fragment.
        Anchor is the first mounted item *after* the current item.
        """
        if self.children:
            idx = self.children.index(other)
            length = len(self.children) - 1
            while 0 <= idx < length:
                idx += 1
                if element := self.children[idx].first():
                    return element

    def set_attribute(self, attr: str, value: Any):
        """
        Set a static attribute. Note that it is not directly applied to
        the element, that will happen in the `create` call.
        """
        self._attributes[attr] = value

    def set_bind(self, attr: str, expression: Callable, immediate=False):
        """
        Set a bind (dynamic attribute) to the value of the expression.
        This will wait to be applied when `create` is called, unless
        `immediate` is True.
        """

        @weak(self)
        def update(self, new):
            if self.element:
                self.renderer.set_attribute(self.element, attr, new)
            elif self.props:
                self.props[attr] = new

        self._watchers[f"bind:{attr}"] = watch(
            expression,
            update,
            immediate=immediate,
        )

    def set_bind_dict(self, name: str, expression: Callable[[], dict[str, Any]]):
        """
        Set dynamic attributes for all of the keys in the value of the expression.
        Since there might be more than one dict bound, the name is used to discern
        between them.

        The dict of the expression will be watched for the keys. For each new key,
        `set_bind` is called to create a dynamic attribute for the value of that
        key. When a key is removed, then the specific watcher is removed and some
        cleanup performed.
        """

        @weak(self)
        def update(self, new: set[str], old: set[str] | None):
            for attr in new - (old or set()):
                self.set_bind(
                    attr,
                    lambda: expression()[attr],
                    immediate=bool(self.element or self.props),
                )

            for attr in (old or set()) - new:
                del self._watchers[f"bind:{attr}"]
                # Perform cleanup
                if self.element:
                    self.renderer.remove_attribute(self.element, attr, None)
                elif self.props:
                    del self.props[attr]

        self._watchers[f"bind_dict:{name}"] = watch(
            lambda: set(expression().keys()),
            update,
            immediate=True,
            deep=True,
        )

    def set_type(self, expression: Callable[[], str | Callable]):
        """
        Set a dynamic type/tag based on the expression.
        """

        @weak(self)
        def update_type(self, tag):
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

    def set_condition(self, expression: Callable[[], bool]):
        """
        Set a expression that determines whether this fragment
        should show up or not.
        """
        self.condition = expression

    def set_event(self, event: str, handler: Callable[[], Any]):
        """
        Set a handler for an event.
        """
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

    def mount(self, target: DomElement, anchor: DomElement | None = None):
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
        elif self.props:
            self.props = None

        # TODO: maybe control flow fragments needs another custom 'parenting'
        # solution where the control flow fragment keeps references to the
        # 'child' elements
        # if self.parent and not isinstance(self.parent, ControlFlowFragment):
        #     if self in self.parent.children:
        #         self.parent.children.remove(self)


class ControlFlowFragment(Fragment):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def mount(self, target: DomElement, anchor: DomElement | None = None):
        self.target = target

        @weak(self)
        def update_fragment(self, new: Fragment | None, old: Fragment | None):
            if old:
                old.unmount()
            if new:
                anch = anchor
                if anch is None and self.parent:
                    anch = self.parent.anchor(self)
                new.mount(self.target, anch)

        self._watchers["control_flow"] = watch(
            self._active_child,
            update_fragment,
            deep=True,
            immediate=True,
        )

    def _active_child(self) -> Fragment | None:
        for child in self.children:
            if child.condition is not None:
                if child.condition():
                    return child
            else:
                return child


class Removed:
    """
    Type (empty) that is used a special return item from
    a watcher callback to indicate that an item was removed
    from a reactive expression.
    """

    pass


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
        super().__init__(*args, **kwargs)
        self.create_fragment: Callable[[], Fragment] | None = None
        self.patch_fragment: Callable | None = None
        self.expression: Callable[[], list[Any]] | None = None
        self.is_keyed: bool = False

    def set_create_fragment(
        self, create_fragment: Callable[[], Fragment], is_keyed: bool
    ):
        self.create_fragment = create_fragment
        self.is_keyed = is_keyed

    def set_patch_fragment(self, patch_fragment: Callable):
        self.patch_fragment = patch_fragment

    def set_expression(self, expression: Callable[[], list[Any]] | None):
        self.expression = expression

    def mount(self, target: Any, anchor: Any | None = None):
        self.target = target

        @computed
        def expression():
            result = self.expression()
            if not hasattr(result, "__len__"):
                return list(result)
            return result

        @weak(self)
        def update_length(self, new: int, old: int | None):
            if old is None:
                old = 0
            if new > old:
                # Add new watchers for new indices
                for i in range(old, new):

                    @weak(self)
                    def value_at_index(self, i=i):
                        value = expression()
                        if i < len(value):
                            return value[i]
                        return Removed

                    @weak(self)
                    def update_for_value_at_index(self, new, old, i=i):
                        if new is Removed:
                            # Unmount fragment here and remove from parent
                            if i < len(self.children):
                                fragment = self.children.pop(i)
                                fragment.unmount()
                                fragment.parent
                            return

                    @weak(self)
                    def index_in_value(self, i=i):
                        value = expression()
                        if i < len(value):
                            return value[i]

                    # fragment = self.create_fragment(lambda i=i: self.expression()[i])
                    fragment = self.create_fragment(index_in_value)
                    # self.children.append(fragment)
                    # fragment.parent = self
                    fragment.mount(target)

                    self._watchers[f"list:{i}"] = watch(
                        value_at_index,
                        update_for_value_at_index,
                        immediate=True,
                        deep=True,
                    )
            elif new < old:
                # Remove extra watchers
                for i in range(old, new):
                    key = f"list:{i}"
                    del self._watchers[key]

        @weak(self)
        def expression_length(self):
            return len(expression())

        # For non-keyed lists.
        self._watchers["list_length"] = watch(
            expression_length,
            update_length,
            immediate=True,
        )
        # TODO: for keyed lists: watch a list of keys instead of indices
        # TODO: but maybe first detect whether a keyed list is used?


class ComponentFragment(Fragment):
    def __init__(self, *args, props=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.component: Component = None
        self.fragment: Fragment = None
        self.props: Proxy | None = props
        assert "tag" not in kwargs or callable(kwargs["tag"])

    def create(self):
        if self.tag is None:
            return

        if self.props is None:
            self.props = reactive({})
        # Set static attributes
        self.props.update(self._attributes)

        # Set dynamic attributes
        for key, watcher in self._watchers.items():
            if key.startswith("bind:"):
                _, attr = key.split(":")
                self.props[attr] = watcher.value

        self.component = self.tag(self.props)
        self.fragment = self.component.render(self.renderer)
        self.fragment.parent = self
        self.children.append(self.fragment)

        # Add all event handlers
        for event, handler in self._events.items():
            self.component.add_event_handler(event, handler)

    def mount(self, target: DomElement, anchor: DomElement | None = None):
        self.target = target
        self.create()

        if self.fragment:
            self.fragment.mount(target, anchor)
        else:
            for child in self.children:
                child.mount(self.element or target, anchor)
