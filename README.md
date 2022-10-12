# Kolla 📓

Reactive user interfaces.

> The word [Kollay](https://en.wikipedia.org/wiki/Kollay) is derived from the Greek word _koll_ or _kolla_, meaning glue, and graph, meaning the activity of drawing.

Unholy marriage of concepts from [Svelte](https://svelte.dev), [Vue](https://vuejs.org) and [Collagraph](https://github.com/fork-tongue/collagraph).

* 'No virtual DOM approach' from Svelte
* Syntax for SFC (`.kolla`) from Vue
* Renderers from Collagraph (PySide6, Pygfx, PyScript)


## Features

Write your Python interfaces in a declarative manner with plain render functions, component classes or even single-file components using Svelte-like syntax, but with Python!

* Reactivity (made possible by leveraging [observ](https://github.com/fork-tongue/observ))
* Single-file components with Vue-like syntax (`.kolla` files)
* Class components with local state and life-cycle methods/hooks
* Custom renderers

Here is an example that shows a simple counter:

```python
from PySide6 import QtWidgets
import kolla
from kolla.sfc import sfc

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
import kolla

class Counter(kolla.Component):
    def __init__(self, props):
        super().__init__(props)
        self.state["count"] = 0

    def bump(self):
        self.state["count"] += 1
</script>
"""
Counter, module = sfc.load_from_string(source)

# Create a Kolla instance with a PySide renderer 
# and register with the Qt event loop
gui = kolla.Kolla(
    renderer=kolla.PySideRenderer(),
    event_loop_type=kolla.EventLoopType.QT,
)
# Render the function component into a container 
# (in this case the app but can be another widget)
app = QtWidgets.QApplication()
gui.render(Counter, app)
app.exec()
```

For more examples, please take a look at the [examples folder](examples).

Currently there are four renderers:

* [PysideRenderer](kolla/renderers/pyside_renderer.py): for rendering PySide6 applications
* [PygfxRenderer](kolla/renderers/pygfx_renderer.py): for rendering 3D graphic scenes with [Pygfx](https://github.com/pygfx/pygfx)
* [DomRenderer](kolla/renderers/dom_renderer.py): for rendering to HTML DOM with [PyScript](http://pyscript.net)
* [DictRenderer](kolla/renderers/dict_renderer.py): for testing purposes

It is possible to create a custom `Renderer` using the [Renderer](kolla/renderers/__init__.py) interface, to render to other UI frameworks, for instance [wxPython](https://wxpython.org) and [GTK](https://pygobject.readthedocs.io/en/latest/) or any other dynamic tree-like structure that you can think of.


## Notable differences from Vue

The root template tag is not required for components and can have multiple elements:

```html
<widget>
</widget>
<button />

<script>
import kolla

class Example(Component):
    pass
</script>
```
