from collections.abc import Callable
from typing import Any

from observ import scheduler

from kolla.component import Component
from kolla.renderers import Renderer
from kolla.types import EventLoopType


class Kolla:
    def __init__(
        self,
        renderer,
        *,
        event_loop_type: EventLoopType = None,
    ):
        if not isinstance(renderer, Renderer):
            raise TypeError(f"Expected a Renderer but got a {type(renderer)}")
        self.renderer = renderer
        if not event_loop_type:
            event_loop_type = (
                renderer.preferred_event_loop_type() or EventLoopType.DEFAULT
            )
        self.event_loop_type = event_loop_type
        if self.event_loop_type is EventLoopType.QT:
            scheduler.register_qt()
        elif self.event_loop_type is EventLoopType.DEFAULT:
            import asyncio

            def request_flush():
                loop = asyncio.get_event_loop_policy().get_event_loop()
                loop.call_soon(scheduler.flush)

            scheduler.register_request_flush(request_flush)
        else:
            scheduler.register_request_flush(scheduler.flush)

    def render(self, component: Callable[[dict], Component], target: Any, state=None):
        """
        target: DOM element/instance to render into.
        """
        instance = component(state or {})

        # breakpoint()
        self.component = instance.render(self.renderer)
        self.component.mount(target)
