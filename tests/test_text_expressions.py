import pytest
from observ import reactive

from kolla import EventLoopType, Kolla
from kolla.renderers import DictRenderer


@pytest.mark.xfail
def test_simple_text(parse_source):
    App, _ = parse_source(
        """
        Hello
        """
    )

    container = {"type": "root"}
    gui = Kolla(
        renderer=DictRenderer(),
        event_loop_type=EventLoopType.SYNC,
    )
    gui.render(App, container)

    assert container["children"][0] == {"type": "TEXT_ELEMENT", "text": "Hello"}


def test_simple_text_in_tree(parse_source):
    App, _ = parse_source(
        """
        <p>
          Hello
        </p>
        """
    )

    container = {"type": "root"}
    gui = Kolla(
        renderer=DictRenderer(),
        event_loop_type=EventLoopType.SYNC,
    )
    gui.render(App, container)

    paragraph = container["children"][0]
    assert paragraph["type"] == "p"
    assert paragraph["children"][0] == {"type": "TEXT_ELEMENT", "text": "Hello"}


@pytest.mark.xfail
def test_dynamic_text(parse_source):
    App, _ = parse_source(
        """
        <p>
          prefix {{ message }} { message } suffix
        </p>

        <script>
        message = ""
        </script>
        """
    )

    state = reactive({"message": "Hello"})
    container = {"type": "root"}
    gui = Kolla(
        renderer=DictRenderer(),
        event_loop_type=EventLoopType.SYNC,
    )
    gui.render(App, container)

    paragraph = container["children"][0]
    assert paragraph["type"] == "p"
    assert paragraph["children"][0] == {
        "type": "TEXT_ELEMENT",
        "text": "prefix Hello { message } suffix",
    }

    state["message"] = "foo"

    assert paragraph["children"][0] == {
        "type": "TEXT_ELEMENT",
        "text": "prefix foo { message } suffix",
    }
