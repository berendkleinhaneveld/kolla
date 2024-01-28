from abc import ABCMeta, abstractmethod
from typing import Any, Callable, Optional

from kolla.types import EventLoopType


class Renderer(metaclass=ABCMeta):  # pragma: no cover
    """Abstract base class for renderers"""

    def preferred_event_loop_type(self) -> Optional[EventLoopType]:
        return None

    @abstractmethod
    def create_element(self, type: str) -> Any:
        """Create an element for the given type."""
        pass

    @abstractmethod
    def create_text_element(self) -> Any:
        """Create a text element."""
        pass

    @abstractmethod
    def insert(self, el: Any, parent: Any, anchor: Any = None):
        """
        Add element `el` as a child to the element `parent`.
        If an anchor is specified, it inserts `el` before the `anchor`
        element.
        """
        pass

    @abstractmethod
    def remove(self, el: Any, parent: Any):
        """Remove the element `el` from the children of the element `parent`."""
        pass

    @abstractmethod
    def set_element_text(self, el: Any, value: str):
        """Set the text of a text element."""
        pass

    @abstractmethod
    def set_attribute(self, el: Any, attr: str, value: Any):
        """Set the attribute `attr` of the element `el` to the value `value`."""
        pass

    @abstractmethod
    def remove_attribute(self, el: Any, attr: str, value: Any):
        """Remove the attribute `attr` from the element `el`."""
        pass

    @abstractmethod
    def add_event_listener(self, el: Any, event_type: str, value: Callable):
        """Add event listener for `event_type` to the element `el`."""
        pass

    @abstractmethod
    def remove_event_listener(self, el: Any, event_type: str, value: Callable):
        """Remove event listener for `event_type` to the element `el`."""
        pass
