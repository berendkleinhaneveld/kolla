from observ import reactive
import pytest

from kolla import EventLoopType, Kolla
from kolla.renderers import DictRenderer


@pytest.mark.xfail
def test_component_tag(parse_source):
    App, _ = parse_source(
        """
        <SubComponent />

        <script>
        import kolla


        class SubComponent(kolla.Component):
            def render(self):
                from kolla.fragment import (
                    ControlFlowFragment,
                    ComponentFragment,
                    ListFragment,
                    Fragment,
                )

                component = ComponentFragment(renderer)
                sub0 = Fragment(renderer, tag="sub", parent=component)
                return component


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
    assert container["children"][0]["type"] == "sub"


@pytest.mark.xfail
def test_component_tag_props(parse_source):
    App, _ = parse_source(
        """
        <SubComponent
          :value="foo"
        />

        <script>
        import kolla


        class SubComponent(kolla.Component):
            def render(self):
                from kolla.fragment import (
                    ControlFlowFragment,
                    ComponentFragment,
                    ListFragment,
                    Fragment,
                )

                component = ComponentFragment(renderer)
                sub0 = Fragment(renderer, tag="sub", parent=component)
                sub0.set_bind("value", lambda: self._lookup("value", globals()))
                return component


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
    assert container["children"][0]["type"] == "sub"
    assert container["children"][0]["attrs"]["value"] == "foo"

    state["foo"] = "bar"

    assert container["children"][0]["attrs"]["value"] == "bar"
