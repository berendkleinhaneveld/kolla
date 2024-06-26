from observ import reactive

from kolla import EventLoopType, Kolla
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


def test_directive_else_if_surrounded(parse_source):
    App, _ = parse_source(
        """
        <before />
        <foo v-if="foo" />
        <bar v-else-if="bar" />
        <after />

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

    assert len(container["children"]) == 2
    assert container["children"][0]["type"] == "before"
    assert container["children"][1]["type"] == "after"

    state["foo"] = True

    assert len(container["children"]) == 3
    assert container["children"][0]["type"] == "before"
    assert container["children"][1]["type"] == "foo"
    assert container["children"][2]["type"] == "after"

    state["bar"] = True

    assert len(container["children"]) == 3
    assert container["children"][0]["type"] == "before"
    assert container["children"][1]["type"] == "foo"
    assert container["children"][2]["type"] == "after"

    state["foo"] = False

    assert len(container["children"]) == 3
    assert container["children"][0]["type"] == "before"
    assert container["children"][1]["type"] == "bar"
    assert container["children"][2]["type"] == "after"

    state["bar"] = False

    assert len(container["children"]) == 2
    assert container["children"][0]["type"] == "before"
    assert container["children"][1]["type"] == "after"

    state["bar"] = True

    assert len(container["children"]) == 3
    assert container["children"][0]["type"] == "before"
    assert container["children"][1]["type"] == "bar"
    assert container["children"][2]["type"] == "after"


def test_directive_else_if_combined(parse_source):
    App, _ = parse_source(
        """
        <foo v-if="foo" />
        <bar v-else-if="bar" />
        <baz v-if="baz" />
        <boa v-else-if="boa" />

        <script>
        import kolla

        class App(kolla.Component):
            pass
        </script>
        """
    )
    state = reactive(
        {
            "foo": False,
            "bar": False,
            "baz": False,
            "boa": False,
        }
    )
    container = {"type": "root"}
    gui = Kolla(
        renderer=DictRenderer(),
        event_loop_type=EventLoopType.SYNC,
    )
    gui.render(App, container, state=state)

    assert "children" not in container

    state["boa"] = True

    def types():
        return [child["type"] for child in container["children"]]

    assert types() == ["boa"]

    state["bar"] = True

    assert types() == ["bar", "boa"]

    state["foo"] = True

    assert types() == ["foo", "boa"]

    state["baz"] = True
    state["foo"] = False

    assert types() == ["bar", "baz"]
