from importlib.metadata import version

from .kolla import Kolla  # noqa: F401
from .renderers import *  # noqa: F401, F403
from .sfc import importer  # noqa: F401, I100
from .types import EventLoopType  # noqa: F401

__version__ = version("kolla")
