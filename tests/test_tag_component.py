from observ import reactive

from kolla import EventLoopType, Kolla
from kolla.renderers import DictRenderer


def test_component_tag(parse_source):
    App, _ = parse_source(
        """
        <SubComponent />

        <script>
        import kolla


        class SubComponent(kolla.Component):
            def render(self, renderer):
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
    assert container["children"][0]["type"] == "sub", container


def test_component_tag_props_and_events(parse_source):
    App, _ = parse_source(
        """
        <el
          :count="action_count"
        >
          <SubComponent
            val="foo"
            :value="bar"
            :other="baz"
            @action="bump"
          />
        </el>

        <script>
        import kolla


        class SubComponent(kolla.Component):
            def render(self, renderer):
                from kolla.fragment import (
                    ControlFlowFragment,
                    ComponentFragment,
                    ListFragment,
                    Fragment,
                )

                # <sub
                #   :subval="val"
                #   :subvalue="value"
                #   :subother="other"
                #   @subaction="self.emit('action')"
                # />
                component = ComponentFragment(renderer)
                sub0 = Fragment(renderer, tag="sub", parent=component)
                sub0.set_bind("subval", lambda: self._lookup("val", globals()))
                sub0.set_bind("subvalue", lambda: self._lookup("value", globals()))
                sub0.set_bind("subother", lambda: self._lookup("other", globals()))
                sub0.add_event("subaction", lambda: self.emit("action"))
                return component


        class App(kolla.Component):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.state["action_count"] = 0

            def bump(self):
                self.state["action_count"] += 1
        </script>
        """
    )

    state = reactive({"bar": "foo", "baz": "baz"})
    container = {"type": "root"}
    gui = Kolla(
        renderer=DictRenderer(),
        event_loop_type=EventLoopType.SYNC,
    )
    gui.render(App, container, state=state)

    assert len(container["children"]) == 1
    el = container["children"][0]
    assert el["type"] == "el"
    assert len(el["children"]) == 1
    sub = el["children"][0]
    assert sub["type"] == "sub"
    assert sub["attrs"]["subval"] == "foo"
    assert sub["attrs"]["subvalue"] == "foo"
    assert sub["attrs"]["subother"] == "baz"

    state["bar"] = "bar"

    assert sub["attrs"]["subvalue"] == "bar"

    state["baz"] = "blaat"

    assert sub["attrs"]["subother"] == "blaat"

    # Check that events work
    assert el["attrs"]["count"] == 0
    assert "subaction" in sub["handlers"], sub["handlers"]
    for handler in sub["handlers"]["subaction"]:
        handler()

    assert el["attrs"]["count"] == 1
