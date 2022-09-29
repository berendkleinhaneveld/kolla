from kolla import Kolla, EventLoopType
from kolla.renderers import DictRenderer


def test_basic_dict_renderer(parse_source):
    App, _ = parse_source(
        """
        <template>
          <foo />
        </template>

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

    assert len(container["children"]) == 1
    assert container["children"][0]["type"] == "foo"
