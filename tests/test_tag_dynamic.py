from observ import reactive

from kolla import EventLoopType, Kolla
from kolla.renderers import DictRenderer
from kolla.renderers.dict_renderer import format_dict


def test_dynamic_component_tag(parse_source):
    App, _ = parse_source(
        """
        <component :is="foo" />

        <script>
        import kolla

        class App(kolla.Component):
            pass
        </script>
        """
    )

    state = reactive({"foo": "foo"})
    container = {"type": "root"}
    gui = Kolla(
        renderer=DictRenderer(),
        event_loop_type=EventLoopType.SYNC,
    )
    gui.render(App, container, state=state)

    assert len(container["children"]) == 1
    assert container["children"][0]["type"] == "foo"

    state["foo"] = "bar"

    assert len(container["children"]) == 1
    assert container["children"][0]["type"] == "bar"


def test_dynamic_component_tag_anchor(parse_source):
    App, _ = parse_source(
        """
        <first />
        <component :is="foo" />
        <last />

        <script>
        import kolla

        class App(kolla.Component):
            pass
        </script>
        """
    )

    state = reactive({"foo": "foo"})
    container = {"type": "root"}
    gui = Kolla(
        renderer=DictRenderer(),
        event_loop_type=EventLoopType.SYNC,
    )
    gui.render(App, container, state=state)

    assert len(container["children"]) == 3
    assert container["children"][0]["type"] == "first", format_dict(container)
    assert container["children"][1]["type"] == "foo", format_dict(container)
    assert container["children"][2]["type"] == "last", format_dict(container)

    state["foo"] = "bar"

    assert len(container["children"]) == 3
    assert container["children"][0]["type"] == "first", format_dict(container)
    assert container["children"][1]["type"] == "bar", format_dict(container)
    assert container["children"][2]["type"] == "last", format_dict(container)
