from kolla.types import EventLoopType


class Scheduler:
    def __init__(self):
        # TODO: make it possible to configure scheduler type
        self.queue = []
        self.event_loop_type = EventLoopType.SYNC

    def add(self, component):
        if component not in self.queue:
            self.queue.append(component)
        if self.event_loop_type == EventLoopType.SYNC:
            self.flush()

    def flush(self):
        while self.queue:
            component = self.queue.pop(0)
            component.flush_update()
