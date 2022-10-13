from observ import reactive
import pytest

from kolla import EventLoopType, Kolla
from kolla.renderers import DictRenderer


@pytest.mark.xfail
def test_directive_else_if_root(parse_source):
    App, _ = parse_source(
        """
        <foo v-if="foo" />
        <bar v-else-if="bar" />

        <script>
        foo = True
        bar = True
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


@pytest.mark.xfail
def test_directive_else_if_surrounded(parse_source):
    App, _ = parse_source(
        """
        <before />
        <foo v-if="foo" />
        <bar v-else-if="bar" />
        <after />

        <script>
        foo = True
        bar = True
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


@pytest.mark.xfail
def test_directive_else_if_combined(parse_source):
    App, _ = parse_source(
        """
        <foo v-if="foo" />
        <bar v-else-if="bar" />
        <baz v-if="baz" />
        <boa v-else-if="boa" />

        <script>
        foo = bar = baz = boa = True
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

    assert len(container["children"]) == 1
    assert container["children"][0]["type"] == "boa"

    state["bar"] = True

    assert len(container["children"]) == 2
    assert container["children"][0]["type"] == "bar"
    assert container["children"][1]["type"] == "boa"

    state["foo"] = True

    assert len(container["children"]) == 2
    assert container["children"][0]["type"] == "foo"
    assert container["children"][1]["type"] == "boa"

    state["baz"] = True
    state["foo"] = False

    assert len(container["children"]) == 2
    assert container["children"][0]["type"] == "bar"
    assert container["children"][1]["type"] == "baz"
