import pytest

from kolla import DictRenderer, EventLoopType, Kolla


@pytest.mark.xfail
def test_refs(parse_source):
    App, _ = parse_source(
        """
        <item ref="item" :value="value" />

        <script>
        from kolla import ref, on_mount

        item = ref()

        value = False

        @on_mount
        def mounted():
            if isinstance(item, dict):
                value = True
        </script>
        """
    )

    container = {"type": "root"}
    gui = Kolla(
        renderer=DictRenderer(),
        event_loop_type=EventLoopType.SYNC,
    )
    gui.render(App, container)

    item = container["children"][0]
    assert item["attrs"]["value"] is True
