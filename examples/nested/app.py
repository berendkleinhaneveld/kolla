from item import Item

from kolla import DictRenderer, EventLoopType, Kolla
from kolla.runtime import Component, Fragment, create_component, mount_component


def create_fragment(context: dict, renderer) -> Fragment:
    widget_0 = None
    button_0 = None
    item_0 = Item({"renderer": renderer})
    __parent = None

    def create():
        nonlocal widget_0, button_0
        widget_0 = renderer.create_element("widget")
        button_0 = renderer.create_element("button")
        renderer.add_event_listener(button_0, "clicked", context["toggle"])
        create_component(item_0.fragment)

    def mount(parent, anchor=None):
        nonlocal __parent
        __parent = parent
        renderer.insert(widget_0, parent, anchor)
        renderer.insert(button_0, widget_0, anchor)
        mount_component(item_0, widget_0, anchor)

    def update(context, dirty):
        item_0_changes = {}
        if "value" in dirty:
            item_0_changes["value"] = context["value"]
        item_0.set(item_0_changes)

    def destroy():
        # renderer.remove(__element, __parent)
        renderer.remove_event_listener(button_0, "@clicked", context["toggle"])

    return Fragment(create, mount, update, destroy)


def instance(__self, __props, __invalidate):
    value = __props.get("value", __props.get("value", "foo"))

    def toggle():
        nonlocal value
        value = "foo" if value != "foo" else "bar"
        __invalidate("value", value)

    return {"value": value, "toggle": toggle}


class App(Component):
    def __init__(self, options=None, props=None):
        super().__init__(options, instance, create_fragment, props=props)


if __name__ == "__main__":
    container = {"type": "root"}
    gui = Kolla(
        renderer=DictRenderer(),
        event_loop_type=EventLoopType.SYNC,
    )
    gui.render(App, container)

    assert container["children"][0]["type"] == "widget"

    item = container["children"][0]["children"][0]
    assert item["type"] == "item", container
    assert item["attrs"]["value"] == "foo"
