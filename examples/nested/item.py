from kolla.runtime import (  # create_component,; destroy_component,; mount_component,
    Component,
    Fragment,
)


def create_fragment(context: dict, renderer) -> Fragment:
    item_0 = None
    __parent = None

    def create():
        nonlocal item_0
        item_0 = renderer.create_element("item")
        renderer.set_attribute(item_0, "value", context["value"])

    def mount(parent, anchor=None):
        nonlocal __parent
        __parent = parent
        renderer.insert(item_0, parent, anchor)

    def update(context, dirty):
        if "value" in dirty:
            renderer.set_attribute(item_0, "value", context["value"])

    def destroy():
        pass
        # renderer.remove(__element, __parent)

    return Fragment(create, mount, update, destroy)


def instance(__self, __props, __invalidate):
    value = __props.get("value", None)
    return {"value": value}


class Item(Component):
    def __init__(self, options=None, props=None):
        super().__init__(options, instance, create_fragment, props=props)
