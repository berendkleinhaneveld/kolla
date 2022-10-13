import pytest

from kolla import EventLoopType, Kolla
from kolla.renderers import DictRenderer


def test_static_attributes(parse_source):
    App, _ = parse_source(
        """
        <app foo="bar" />
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


def test_static_attributes_nested_elements(parse_source):
    App, _ = parse_source(
        """
        <app foo="bar">
          <item text="baz" />
        </app>
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


def test_static_bool_attribute(parse_source):
    App, _ = parse_source(
        """
        <app foo />
        """
    )

    container = {"type": "root"}
    gui = Kolla(
        renderer=DictRenderer(),
        event_loop_type=EventLoopType.SYNC,
    )
    gui.render(App, container)

    app = container["children"][0]
    assert app["attrs"]["foo"] is True
