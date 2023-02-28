from enum import Enum


class EventLoopType(Enum):
    ASYNC = "asyncio"
    QT = "Qt"
    SYNC = "sync"
