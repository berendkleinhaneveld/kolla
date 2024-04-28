"""
Example of how to render lists, tables and trees.
"""

from observ import reactive
from PySide6 import QtWidgets
from wgpu.gui.qt import WgpuCanvas

import collagraph
from examples.pygfx.app_point_cloud import Example

if __name__ == "__main__":
    app = QtWidgets.QApplication()

    renderer = collagraph.PySideRenderer()
    renderer.register("wgpucanvas", WgpuCanvas)
    gui = collagraph.Collagraph(renderer=renderer)

    state = reactive({"count": 1000})

    # Define Qt structure and map state to the structure
    # Pass in the app as a container. Can actually be any truthy object
    gui.render(Example, app, state=state)
    app.exec()
