from observ import reactive

from kolla import Kolla, EventLoopType
from kolla.renderers import DictRenderer


def test_dynamic_component_type(parse_source):
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
