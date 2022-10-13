from observ import reactive
import pytest

from kolla import EventLoopType, Kolla
from kolla.renderers import DictRenderer


@pytest.mark.xfail
def test_dynamic_component_tag(parse_source):
    App, _ = parse_source(
        """
        <component :is="foo" />

        <script>
        foo = "template"
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
