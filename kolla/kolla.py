from observ import scheduler

from kolla.renderers import Renderer
from kolla.types import (
    EventLoopType,
)


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

    def render(self, component, state, container):
        instance = component(state)

        self.elements = instance.render(self.renderer)
        for el in self.elements:
            el.construct(self.renderer, container)
