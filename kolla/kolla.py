from typing import Any

from kolla.renderers import Renderer
from kolla.runtime.scheduler import Scheduler
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
        self.renderer.scheduler = Scheduler()

        if not event_loop_type:
            event_loop_type = (
                renderer.preferred_event_loop_type() or EventLoopType.DEFAULT
            )
        self.renderer.scheduler.event_loop_type = event_loop_type

    def render(self, component, target: Any, state=None):
        """
        target: DOM element/instance to render into.
        """
        # TODO: pass in state
        options = {
            "renderer": self.renderer,
            "target": target,
        }
        self.component = component(options)
