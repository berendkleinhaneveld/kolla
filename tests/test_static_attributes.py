import pytest

from kolla import Kolla, EventLoopType
from kolla.renderers import DictRenderer


def test_static_attributes(parse_source):
    App, _ = parse_source(
        """
        <app foo="bar" baz />

        <script>
        import kolla

        class App(kolla.Component):
            pass
        </script>
        """
    )

    container = {"type": "root"}
    gui = Kolla(
        renderer=DictRenderer(),
        event_loop_type=EventLoopType.SYNC,
    )
    gui.render(App, container)

    app = container["children"][0]
    assert app["attrs"]["foo"] == "bar"
    assert app["attrs"]["baz"] is True


def test_static_attributes_nested_elements(parse_source):
    App, _ = parse_source(
        """
        <app foo="bar">
          <item text="baz" />
        </app>

        <script>
        import kolla

        class App(kolla.Component):
            pass
        </script>
        """
    )

    container = {"type": "root"}
    gui = Kolla(
        renderer=DictRenderer(),
        event_loop_type=EventLoopType.SYNC,
    )
    gui.render(App, container)

    app = container["children"][0]
    assert app["attrs"]["foo"] == "bar"

    item = app["children"][0]
    assert item["attrs"]["text"] == "baz"


@pytest.mark.xfail
def test_static_integer_attribute(parse_source):
    App, _ = parse_source(
        """
        <app foo=2 />

        <script>
        import kolla

        class App(kolla.Component):
            pass
        </script>
        """
    )

    container = {"type": "root"}
    gui = Kolla(
        renderer=DictRenderer(),
        event_loop_type=EventLoopType.SYNC,
    )
    gui.render(App, container)

    app = container["children"][0]
    assert app["attrs"]["foo"] == 2
