from kolla import Kolla, EventLoopType
from kolla.renderers import DictRenderer


def test_reactive_element_with_events(parse_source):
    App, _ = parse_source(
        """
        <count
          :count="count"
          @bump="bump"
        />

        <script>
        import kolla

        class App(kolla.Component):
            def __init__(self, props):
                super().__init__(props)
                self.state["count"] = 0

            def bump(self):
                self.state["count"] += 1
        </script>
        """
    )

    container = {"type": "root"}
    gui = Kolla(
        renderer=DictRenderer(),
        event_loop_type=EventLoopType.SYNC,
    )

    gui.render(App, container)

    count = container["children"][0]
    assert count["type"] == "count"
    assert count["attrs"]["count"] == 0
    assert len(count["handlers"]["bump"]) == 1

    # Update state by triggering all listeners, which should trigger a re-render
    for listener in count["handlers"]["bump"]:
        listener()

    assert count["attrs"]["count"] == 1
