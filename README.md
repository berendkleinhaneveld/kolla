# Kolla 📓

Unholy marriage of concepts from [Svelte](https://svelte.dev), [Vue](https://vuejs.org) and [Collagraph](https://github.com/fork-tongue/collagraph).

> The word [Kollay](https://en.wikipedia.org/wiki/Kollay) is derived from the Greek word _koll_ or _kolla_, meaning glue, and graph, meaning the activity of drawing.

* 'No virtual DOM approach' from Svelte
* Syntax for SFC (`.kolla`) from Vue
* Renderers from Collagraph (PySide6, Pygfx, PyScript)

Currently this is being developed as a Proof-of-Concept in order to learn more about how Svelte works.


## Features

Write your Python interfaces in a declarative manner as single-file components using Vue-like syntax, but with Python!

* Reactivity (mostly Svelte-style, partly made possible by leveraging [observ](https://github.com/fork-tongue/observ))
* Single-file components with Vue-like syntax (`.kolla` files) and life-cycle methods
* Custom renderers

Here is an example that shows a simple counter:

```python
from PySide6 import QtWidgets
import kolla

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
Counter, module = kolla.sfc.load_from_string(source)

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


# Progress

- [ ] Tags
    - [X] Static tags
    - [X] Component tags
    - [ ] Dynamic tags (`<component is="...">`)
    - [ ] Template tags
- [ ] Attributes and props
    - [X] Static attributes
    - [X] Boolean attributes
    - [ ] Bound attributes
        - [X] Single attributes (v-bind: / :)
        - [ ] Bound dictionaries/objects (v-bind)
- [ ] Text expressions
    - [X] Static text
    - [ ] Dynamic text
    - [ ] Child elements
- [ ] Directives
    - [ ] v-if
    - [ ] v-else-if
    - [ ] v-else
    - [ ] v-for
    - [X] v-on / @ (events)
        - [ ] Event modifiers
- [ ] Slots
    - [ ] Default slot
    - [ ] Named
    - [ ] Default slot content
- [ ] Component life cycle
    - [ ] mounted
    - [ ] updated
    - [ ] before_destroy
- [ ] Component events / emit
- [ ] Render callback
- [ ] Provide / inject (setContext, getContext)
- [ ] Compile to file
    - [ ] Auto-update when .kolla file changed
- [ ] Directly run `.kolla` files
