import pytest

from kolla import DictRenderer, EventLoopType, Kolla


@pytest.mark.xfail
def test_life_cycle(parse_source):
    App, _ = parse_source(
        """
        <app v-if="show" foo="bar" />

        <script>
        from kolla import after_update, on_destroy, on_mounted,

        show = False
        callback = None

        @on_mount
        def mounted():
            callback("mounted")

        @after_update
        def updated():
            callback("updated")

        @on_destroy
        def destroyed():
            callback("destroyed")
        </script>
        """
    )

    result = []

    def callback(value):
        result.append(value)

    state = {"callback": callback, "show": True}
    container = {"type": "root"}
    gui = Kolla(
        renderer=DictRenderer(),
        event_loop_type=EventLoopType.SYNC,
    )
    gui.render(App, container, state=state)

    assert result == []

    state["show"] = True

    assert result == ["mounted", "updated"]

    state["show"] = False

    assert result == ["mounted", "updated", "destroyed"]
