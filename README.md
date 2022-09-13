[![PyPI version](https://badge.fury.io/py/kolla.svg)](https://badge.fury.io/py/kolla)
[![CI status](https://github.com/fork-tongue/kolla/workflows/CI/badge.svg)](https://github.com/fork-tongue/kolla/actions)

# Kolla 📓

Reactive user interfaces.

> The word [Kollay](https://en.wikipedia.org/wiki/Kollay) is derived from the Greek word _koll_ or _kolla_, meaning glue, and graph, meaning the activity of drawing.

Inspired by [Svelte](https://svelte.dev) and [Collagraph](https://github.com/fork-tongue/collagraph).


## Features

Write your Python interfaces in a declarative manner with plain render functions, component classes or even single-file components using Svelte-like syntax, but with Python!

* Reactivity (made possible by leveraging [observ](https://github.com/fork-tongue/observ))
* Single-file components with Vue-like syntax (`.kolla` files)
* Function components
* Class components with local state and life-cycle methods/hooks
* Custom renderers

Here is an example that shows a simple counter, made with a function component:

```python
from PySide6 import QtWidgets
from observ import reactive
import kolla

# Declare some reactive state
state = reactive({"count": 0})

# Define function that adjusts the state
def bump():
    state["count"] += 1

# Declare how the state should be rendered
def Counter(props):
    return kolla.h(
        "widget",
        {},
        kolla.h("label", {"text": f"Count: {props['count']}"}),
        kolla.h("button", {"text": "Bump", "on_clicked": bump}),
    )

# Create a Kolla instance with a PySide renderer 
# and register with the Qt event loop
gui = kolla.Kolla(
    renderer=kolla.PySideRenderer(),
    event_loop_type=kolla.EventLoopType.QT,
)
# Render the function component into a container 
# (in this case the app but can be another widget)
app = QtWidgets.QApplication()
gui.render(kolla.h(Counter, state), app)
app.exec()
```

For more examples, please take a look at the [examples folder](examples).

Currently there are two renderers:

* [PysideRenderer](kolla/renderers/pyside_renderer.py): for rendering PySide6 applications
* [PygfxRenderer](kolla/renderers/pygfx_renderer.py): for rendering 3D graphic scenes with [Pygfx](https://github.com/pygfx/pygfx)

It is possible to create a custom Renderer using the [Renderer](kolla/renderers/__init__.py) interface, to render to other UI frameworks, for instance wxPython, or even the browser DOM.
