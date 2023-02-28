from PySide6 import QtWidgets

import kolla
from examples.simple_counter import SimpleCounter

if __name__ == "__main__":
    # Create a Kolla instance with a PySide renderer
    # and register with the Qt event loop
    gui = kolla.Kolla(
        renderer=kolla.PySideRenderer(),
        event_loop_type=kolla.EventLoopType.QT,
    )
    app = QtWidgets.QApplication()
    gui.render(SimpleCounter, app)
    app.exec()
