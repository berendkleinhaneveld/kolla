import pytest

from kolla import EventLoopType, Kolla
from kolla.renderers import DictRenderer


def test_parser_unclosed_element(parse_source):
    App, _ = parse_source(
        """
        <app>
          <unclosed>
        </app>

        <script>
        import kolla

        class App(kolla.Component):
            pass
        </script>
        """
    )

    gui = Kolla(
        renderer=DictRenderer(),
        event_loop_type=EventLoopType.SYNC,
    )
    container = {"type": "root"}
    gui.render(App, container)

    assert container["children"][0] == {
        "type": "app",
        "children": [
            {"type": "unclosed"},
        ],
    }


def test_parser_unclosed_root_element(parse_source):
    with pytest.raises(ValueError):
        _ = parse_source(
            """
            <app>

            <script>
            import kolla

            class App(kolla.Component):
                pass
            </script>
            """
        )
