from importlib.metadata import version

from .component import Component  # noqa: F401
from .kolla import Kolla  # noqa: F401
from .renderers import *  # noqa: F401, F403
from .sfc import importer  # noqa: F401, I100
from .types import EventLoopType  # noqa: F401

__version__ = version("kolla")


class Block:
    __slots__ = ("create", "mount", "update", "unmount")

    def __init__(self, create, mount, update, unmount):
        self.create = create
        self.mount = mount
        self.update = update
        self.unmount = unmount
