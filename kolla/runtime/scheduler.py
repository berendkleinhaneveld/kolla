from weakref import ref

from kolla.types import EventLoopType


class Scheduler:
    def __init__(self):
        self.queue = []
        self._event_loop_type = None
        self.event_loop_type = EventLoopType.SYNC

    @property
    def event_loop_type(self):
        return self._event_loop_type

    @event_loop_type.setter
    def event_loop_type(self, value):
        if self._event_loop_type != value:
            self._event_loop_type = value

            if self._event_loop_type == EventLoopType.SYNC:
                self._request_flush = self.flush
            elif self._event_loop_type == EventLoopType.ASYNC:
                import asyncio

                def request_flush():
                    loop = asyncio.get_event_loop_policy().get_event_loop()

                    def request():
                        loop.stop()
                        self.flush()

                    loop.call_soon_threadsafe(request)
                    loop.run_forever()

                self._request_flush = request_flush
            elif self._event_loop_type == EventLoopType.QT:
                from PySide6 import QtCore

                self._qt_timer = QtCore.QTimer()
                self._qt_timer.setSingleShot(True)
                self._qt_timer.setInterval(0)

                self._qt_first_run = True

                def request_flush():
                    if not self._qt_first_run:
                        self._qt_timer.timeout.disconnect()
                    else:
                        self._qt_first_run = False

                    weak_self = ref(self)
                    self._qt_timer.timeout.connect(
                        lambda: weak_self() and weak_self().flush()
                    )
                    self._qt_timer.start()

                self._request_flush = request_flush

    def request_flush(self):
        self._request_flush()

    def add(self, component):
        if component not in self.queue:
            self.queue.append(component)

        self.request_flush()

    def flush(self):
        while self.queue:
            component = self.queue.pop(0)
            component.flush_update()
