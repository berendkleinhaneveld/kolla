from PySide6 import QtWidgets

import kolla
from kolla import sfc

# The source normally resides in a .kolla file
# which can be imported like any other python file
# after the `import kolla` line. For this example
# we'll just parse directly from a string.
source = """
<widget>
  <label :text="f'Count: {count}'" />
  <button text="Bump" @clicked="bump" />
</widget>

<script>
count = 0

def bump(self):
    global count
    count += 1
</script>
"""
Counter, module = sfc.load_from_string(source, "Counter")

# Create a Kolla instance with a PySide renderer
# and register with the Qt event loop
gui = kolla.Kolla(
    renderer=kolla.PySideRenderer(),
    event_loop_type=kolla.EventLoopType.QT,
    # event_loop_type=kolla.EventLoopType.ASYNC,
    # event_loop_type=kolla.EventLoopType.SYNC,
)
# Render the function component into a container
# (in this case the app but can be another widget)
app = QtWidgets.QApplication()
gui.render(Counter, app)
app.exec()
