from PySide6 import QtWidgets

import kolla
from kolla.sfc import compiler

# The source normally resides in a .cgx file
# which can be imported like any other python file
# after the `import kolla` line. For this example
# we'll just parse directly from a string.
source = """
<widget>
  <label :text="f'Count: {count}'" />
  <button text="Bump" @clicked="bump" />
</widget>

<script>
import kolla

class Counter(kolla.Component):
    def __init__(self, props):
        super().__init__(props)
        self.state["count"] = 0

    def bump(self):
        self.state["count"] += 1
</script>
"""
Counter, module = compiler.load_from_string(source)

if __name__ == "__main__":
    app = QtWidgets.QApplication()
    # Create a Kolla instance with a PySide renderer
    # and register with the Qt event loop
    gui = kolla.Kolla(renderer=kolla.PySideRenderer())
    # Render the function component into a container
    # (in this case the app but can be another widget)
    gui.render(Counter, app)
    app.exec()
