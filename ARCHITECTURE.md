# Architecture

Kolla will compile `.kolla` files to Python code along the lines of the following example:


```html
<!-- App.kolla -->
<script>
from .nested import Nested

# Global variables can automatically be set as props
bar = "baz"
count = 0

def bump():
    global count
    count += 1
</script>

<element :foo="bar" :count="count">
  <Nested :count="count" />
</element>

```


```python
from kolla.runtime import Component, Fragment

# List of all imports from the script tag
from .nested import Nested


def create_fragment(context: dict, renderer) -> Fragment:
    # Declare list of all the elements in the template
    element_0 = None
    # Declare and instantiate list of all components used
    # in the template
    nested_0 = Nested()
    # And a reference to the parent of the component that
    # gets set in the `mount` function below
    __parent = None

    def create():
        # Start with nonlocal for all elements defined in template
        nonlocal element_0
        # Create all the elements with the renderer
        element_0 = renderer.create_element("item")
        # Set all attributes for each element
        # Note that when there are names in the expressions (values) from
        # the global scope in the script part of the template, the value
        # gets wrapped with a lookup from `context[<name_of_value>]`
        renderer.set_attribute(element_0, "foo", context["bar"])
        renderer.set_attribute(element_0, "count", context["count"])

    def mount(parent, anchor=None):
        # Start with assigning the parent for later access when destroying
        # TODO: we might be able to just pass `parent` to destroy method instead?
        nonlocal __parent
        __parent = parent
        # For each elemeent, insert it to its parent. Elements in the root of the
        # template are added to the provided parent
        renderer.insert(element_0, parent, anchor)

    def update(context, dirty):
        # For each dynamic attribute from which the expression references a
        # variable from the global scope, there needs to be a `if` check to
        # see if any of the referenced variables is dirty.
        # This is just for any plain element, not for components
        if "bar" in dirty:
            renderer.set_attribute(element_0, "foo", context["bar"])
        if "count" in dirty:
            renderer.set_attribute(element_0, "count", context["count"])

        # For all components the $set function should be called, when any
        # of the referenced variables is marked dirty
        ...

    def destroy():
        # Remove all elements from the hierarchy
        renderer.remove(element_0, __parent)
        # Remove all event listeners
        ...
        # Set all element references to None?
        # Of just destroy the fragment?
        ...

    return Fragment(create, mount, update, destroy)


def instance(__self, __props, __invalidate):
    # Converted from the original source:
    #   bar = "baz"
    #   count = 0
    bar = __props.get("bar", "baz")
    count = __props.get("count", 0)

    def bump(self):
        nonlocal count
        count += 1
        __invalidate("count", count)

    def set_props(props):
        # For each of the (global) variables (not the functions),
        # add logic to update the variable from incoming component props
        if "bar" in props:
            value = props["bar"]
            if value != bar:
                nonlocal bar
                bar = value
                __invalidate("bar", bar)
        if "count" in props:
            value = props["count"]
            if value != count:
                nonlocal count
                count = value
                __invalidate("count", count)

    # Add the `set_props` method to the component
    __self.set = set_props

    # Export all variables and functions defined in global scope
    return {"bar": bar, "count": count, "bump": bump}


class App(Component):
    def __init__(self, options=None, props=None):
        super().__init__(options, instance, create_fragment, props=props)
```



```html
<!-- Nested.kolla -->
<script>
count = 0

def bump():
    global count
    count += 1
</script>

<element :count="count" />
```


## IDEAS

What if I take the 'original' `Fragment` idea/concept and properly introduce `context`
for fragments. Together with detailed information from the template, I might be able to
make that work.
A for-loop could have it's own context (in a dict: `Component._context` for instance)
where all values will be wrapped in a `self._lookup()` call with a specified key that
will first lookup the context for that specific for-loop.

For instance, a for-loop gets a unique id: 'for-BDICNK'. The expression for the for-loop
is then evaluated and the outcome is stored in `component._context["for-BDICNK"]`.
Then all the expressions within the for-loop will be wrapped with
`self._lookup("item", ctx="for-BDICNK")`.

Hmm, now that I'm writing this out, this will probably not work like this. Needs one extra
layer of abstraction.
