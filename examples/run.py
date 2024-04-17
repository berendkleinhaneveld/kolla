from observ import scheduler
from PySide6 import QtWidgets

import kolla
from examples.app import App

if __name__ == "__main__":
    app = QtWidgets.QApplication()
    scheduler.register_qt()

    gui = kolla.Kolla(renderer=kolla.PySideRenderer())
    gui.render(App, app, state=None)

    app.exec()
