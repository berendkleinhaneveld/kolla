from importlib.metadata import version

from .component import Component, ListElementComponent  # noqa: F401
from .kolla import Kolla  # noqa: F401
from .renderers import *  # noqa: F403
from .sfc import importer  # noqa: F401
from .types import EventLoopType  # noqa: F401

__version__ = version("kolla")
