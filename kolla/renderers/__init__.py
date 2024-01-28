import importlib

from .dict_renderer import DictRenderer
from .html_renderer import HTMLRenderer
from .renderer import Renderer

__all__ = [
    Renderer.__name__,
    DictRenderer.__name__,
    HTMLRenderer.__name__,
]

if importlib.util.find_spec("js"):  # pragme: no cover
    from .dom_renderer import DomRenderer

    __all__.append(DomRenderer.__name__)

if importlib.util.find_spec("pygfx"):  # pragme: no cover
    from .pygfx_renderer import PygfxRenderer

    __all__.append(PygfxRenderer.__name__)

if importlib.util.find_spec("PySide6"):  # pragme: no cover
    from .pyside_renderer import PySideRenderer

    __all__.append(PySideRenderer.__name__)
