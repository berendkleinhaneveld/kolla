from observ import reactive

from kolla import Kolla, EventLoopType
from kolla.renderers import DictRenderer


def test_directive_if_root(parse_source):
    App, _ = parse_source(
        """
        <app v-if="foo" />

        <script>
        import kolla

        class App(kolla.Component):
            pass
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


def test_directive_if_nested(parse_source):
    App, _ = parse_source(
        """
        <app>
          <item v-if="foo" />
        </app>

        <script>
        import kolla

        class App(kolla.Component):
            pass
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


def test_directive_if_with_children(parse_source):
    App, _ = parse_source(
        """
        <app v-if="foo">
          <item text="foo" />
        </app>

        <script>
        import kolla

        class App(kolla.Component):
            pass
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
    assert app["children"][0]["attrs"]["text"] == "foo"

    state["foo"] = False

    assert "children" not in container
