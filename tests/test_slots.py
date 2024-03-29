import pytest

from kolla import DictRenderer, EventLoopType, Kolla


@pytest.mark.xfail
def test_slots(parse_source):
    App, _ = parse_source(
        """
        <Container>
          <Item value="foo" />
        </Container>

        <script>
        from tests.data.item import Item
        from tests.data.container import Container
        </script>
        """
    )

    container = {"type": "root"}
    gui = Kolla(
        renderer=DictRenderer(),
        event_loop_type=EventLoopType.SYNC,
    )
    gui.render(App, container)

    item = container["children"][0]["children"][0]
    assert item["attrs"]["value"] == "foo"
