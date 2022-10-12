from observ import reactive
import pytest

from kolla import Kolla, EventLoopType
from kolla.renderers import DictRenderer


@pytest.mark.xfail
def test_directive_if_root(parse_source):
    App, _ = parse_source(
        """
        <app v-if="foo" />

        <script>
        foo = True
        </script>
        """
    )

    state = reactive({"foo": False})
    container = {"type": "root"}
    gui = Kolla(
        renderer=DictRenderer(),
        event_loop_type=EventLoopType.SYNC,
    )
    gui.render(App, container, state=state)

    assert "children" not in container

    state["foo"] = True

    assert len(container["children"]) == 1
    assert container["children"][0]["type"] == "app"

    state["foo"] = False

    assert "children" not in container


@pytest.mark.xfail
def test_directive_if_nested(parse_source):
    App, _ = parse_source(
        """
        <app>
          <item v-if="foo" />
        </app>

        <script>
        foo = True
        </script>
        """
    )

    state = reactive({"foo": False})
    container = {"type": "root"}
    gui = Kolla(
        renderer=DictRenderer(),
        event_loop_type=EventLoopType.SYNC,
    )
    gui.render(App, container, state=state)

    app = container["children"][0]
    assert app["type"] == "app"
    assert "children" not in app

    state["foo"] = True

    assert len(app["children"]) == 1
    assert app["children"][0]["type"] == "item"

    state["foo"] = False

    assert "children" not in app


@pytest.mark.xfail
def test_directive_if_with_children(parse_source):
    App, _ = parse_source(
        """
        <app v-if="foo">
          <item text="bar" />
        </app>

        <script>
        foo = True
        </script>
        """
    )

    state = reactive({"foo": False})
    container = {"type": "root"}
    gui = Kolla(
        renderer=DictRenderer(),
        event_loop_type=EventLoopType.SYNC,
    )
    gui.render(App, container, state=state)

    assert "children" not in container

    state["foo"] = True

    app = container["children"][0]
    assert app["type"] == "app"
    assert len(app["children"]) == 1
    assert app["children"][0]["type"] == "item"
    assert app["children"][0]["attrs"]["text"] == "bar"

    state["foo"] = False

    assert "children" not in container


@pytest.mark.xfail
def test_directive_if_surrounded(parse_source):
    App, _ = parse_source(
        """
        <before />
        <app v-if="foo" />
        <after />

        <script>
        foo = True
        </script>
        """
    )

    state = reactive({"foo": False})
    container = {"type": "root"}
    gui = Kolla(
        renderer=DictRenderer(),
        event_loop_type=EventLoopType.SYNC,
    )
    gui.render(App, container, state=state)

    assert len(container["children"]) == 2
    assert container["children"][0]["type"] == "before"
    assert container["children"][-1]["type"] == "after"

    state["foo"] = True

    assert len(container["children"]) == 3
    assert container["children"][1]["type"] == "app"
    assert container["children"][0]["type"] == "before"
    assert container["children"][-1]["type"] == "after"

    state["foo"] = False

    assert len(container["children"]) == 2
    assert container["children"][0]["type"] == "before"
    assert container["children"][-1]["type"] == "after"
