from observ import scheduler
from PySide6 import QtWidgets

import collagraph
from examples.counter import Counter

if __name__ == "__main__":
    app = QtWidgets.QApplication()
    scheduler.register_qt()

    gui = collagraph.Collagraph(renderer=collagraph.PySideRenderer())
    gui.render(Counter, app, state=None)

    app.exec()
