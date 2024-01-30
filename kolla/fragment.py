from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar
from weakref import ref

from observ import computed, reactive, watch_effect
from observ.proxy import Proxy
from observ.watcher import Watcher, watch  # type: ignore

from .component import Component
from .renderers import Renderer
from .weak import weak

DomElement = TypeVar("DomElement")


class Removed:
    """
    Type (empty) that is used a special return item from
    a watcher callback to indicate that an item was removed
    from a reactive expression.
    """

    pass


class Fragment:
    """
    A fragment is something that describes an element as a kind of function.
    In the kolla template, elements are functions that describe what an element
    should be like based on certain input. Directives such as v-if and v-for serve
    as functions that govern a dynamic list of elements.
    """

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
        # Static attributes for the DOM element
        self._attributes: dict[str, str] = {}
        # Events for the DOM element
        self._events: dict[str, Callable] = {}
        # Watchers associated with the DOM element
        self._watchers: dict[str, Watcher] = {}
        # Conditional expression for whether the DOM element should be rendered
        self._condition: Callable | None = None

        # TODO: maybe this next line is a bit nasty, but
        # on the other hand, it makes sure that the
        # relationship between this item and its parent
        # is set correctly
        if parent:
            parent.children.append(self)

        # FIXME: should fragments also be able to be 'anchored'???

    def __repr__(self):
        return f"<{type(self).__name__}({self.tag})>"

    @property
    def parent(self) -> Fragment | None:
        return self._parent() if self._parent else None

    @parent.setter
    def parent(self, parent: Fragment | None):
        # TODO: should this also check that this item is
        # now in the list of the parent's children?
        self._parent = ref(parent) if parent else None

    def first(self) -> DomElement | None:
        """
        Returns the first DOM element (if any), from either itself, or its direct
        decendants, in case of virtual fragments. Should not be deeper since an
        anchor lives in the same depth in the tree.
        """
        if self.element:
            return self.element
        for child in self.children:
            if child.element:
                return child.element

    def anchor(self) -> DomElement | None:
        """
        Returns the fragment that serves as anchor for this fragment.
        Anchor is the first mounted item *after* the current item.
        """
        parent = self.parent
        idx = parent.children.index(self)
        length = len(parent.children) - 1
        while 0 <= idx < length:
            idx += 1
            if element := parent.children[idx].first():
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
            self._set_attr(attr, new)

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
            if old is None:
                old = set()
            for attr in new - old:
                self.set_bind(
                    attr,
                    lambda: expression()[attr],
                    immediate=bool(self._has_content()),
                )

            for attr in old - new:
                del self._watchers[f"bind:{attr}"]
                # Perform cleanup
                self._rem_attr(attr)

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
            anchor = self.anchor()
            self.unmount()
            self.tag = tag
            self.mount(self.target, anchor)

        # Set the tag immediately
        # TODO: In case of a component tag, do we maybe want to wait???
        # So that we can build up a reactive props object or something?
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
        Only during the 'mount' cycle will this condition be 'installed'
        and monitored for its effects.
        """
        self._condition = expression

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

    def _set_attr(self, attr, value):
        if self.element:
            self.renderer.set_attribute(self.element, attr, value)

    def _rem_attr(self, attr):
        if self.element:
            self.renderer.remove_attribute(self.element, attr, None)

    def _remove(self):
        if self.element:
            self.renderer.remove(self.element, self.target)
            self.element = None

    def _has_content(self):
        return bool(self.element)

    def unmount(self):
        for child in self.children:
            child.unmount()

        self._remove()

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
                    anch = self.anchor()
                new.mount(self.target, anch)

        self._watchers["control_flow"] = watch(
            self._active_child,
            update_fragment,
            deep=True,
            immediate=True,
        )

    def _active_child(self) -> Fragment | None:
        for child in self.children:
            if child._condition is not None:
                if child._condition():
                    return child
            else:
                return child


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
        self.expression: Callable[[], list[Any]] | None = None
        self.is_keyed: bool = False

    def set_create_fragment(
        self, create_fragment: Callable[[], Fragment], is_keyed: bool
    ):
        self.create_fragment = create_fragment
        self.is_keyed = is_keyed

    def set_expression(self, expression: Callable[[], list[Any]] | None):
        self.expression = expression

    def mount(self, target: Any, anchor: Any | None = None):
        self.target = target

        # First create a computed value that captures the expression
        # as a list. We use a computed value so that the list is
        # evaluated lazy and is only re-evaluated when needed.
        @computed
        @weak(self)
        def expression(self):
            value = self.expression()
            return value if hasattr(value, "__len__") else list(value)

        @weak(self)
        def update_children(self):
            for i, item in enumerate(expression()):
                if i >= len(self.children):

                    @weak(self)
                    def index_in_value(self, i=i):
                        if i < len(expression()):
                            return expression()[i]

                    # NOTE: I could try and figure out the lambda names
                    # in the expression / self.expression

                    # TODO: create_fragment should contain a reactive object
                    # probably with all the required props. Then within the
                    # 'create_node' method, the binds can be picked from the
                    # reactive object. And we'll need a watcher to update that
                    # reactive object from the 'outside' (so here in this function)

                    fragment = self.create_fragment(index_in_value)
                    self.children.append(fragment)
                    fragment.parent = self
                    fragment.mount(target)

            for index in reversed(range(i + 1, len(self.children))):
                fragment = self.children.pop(index)
                fragment.unmount()
                fragment.parent = None

        # Then we add a watch_effect for the children
        # which adds/removes/updates all the child fragments
        self._watchers["list"] = watch_effect(update_children)

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

    def _set_attr(self, attr, value):
        self.props[attr] = value

    def _rem_attr(self, attr):
        del self.props[attr]

    def _remove(self):
        self.props = None

    def _has_content(self):
        return bool(self.props)
