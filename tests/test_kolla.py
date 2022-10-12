import pytest

from kolla import Kolla, EventLoopType
from kolla.renderers import DictRenderer


def test_basic_dict_renderer(parse_source):
    App, _ = parse_source(
        """
        <app />
        """
    )

    gui = Kolla(
        renderer=DictRenderer(),
        event_loop_type=EventLoopType.SYNC,
    )
    container = {"type": "root"}
    gui.render(App, container)

    assert container["children"][0] == {"type": "app"}


def test_renderer_required():
    # renderer argument is required
    with pytest.raises(TypeError):
        Kolla(event_loop_type=EventLoopType.SYNC)

    # When the renderer argument is passed, it should be a Renderer subclass
    with pytest.raises(TypeError) as e:
        Kolla(
            renderer=True,
            event_loop_type=EventLoopType.SYNC,
        )

    assert "Expected a Renderer" in str(e)
