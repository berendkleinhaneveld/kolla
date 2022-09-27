from observ import reactive

from kolla import Kolla, EventLoopType
from kolla.renderers import DictRenderer


def test_directive_else_if_root(parse_source):
    App, _ = parse_source(
        """
        <foo v-if="foo" />
        <bar v-else-if="bar" />

        <script>
        import kolla

        class App(kolla.Component):
            pass
        </script>
        """
    )

    state = reactive({"foo": False, "bar": False})
    container = {"type": "root"}
    gui = Kolla(
        renderer=DictRenderer(),
        event_loop_type=EventLoopType.SYNC,
    )
    gui.render(App, container, state=state)

    assert "children" not in container

    state["foo"] = True

    assert len(container["children"]) == 1
    assert container["children"][0]["type"] == "foo"

    state["bar"] = True

    assert len(container["children"]) == 1
    assert container["children"][0]["type"] == "foo"

    state["foo"] = False

    assert len(container["children"]) == 1
    assert container["children"][0]["type"] == "bar"

    state["bar"] = False

    assert "children" not in container

    state["bar"] = True

    assert len(container["children"]) == 1
    assert container["children"][0]["type"] == "bar"
