from kolla import DictRenderer, EventLoopType, Kolla


def test_nested_component(parse_source):
    App, _ = parse_source(
        """
        <widget>
          <Item :value="data" />
          <button @clicked="toggle" />
        </widget>

        <script>
        from tests.data.item import Item

        data = "foo"

        def toggle():
            global data
            data = "foo" if data != "foo" else "bar"
        </script>
        """
    )

    container = {"type": "root"}
    gui = Kolla(
        renderer=DictRenderer(),
        event_loop_type=EventLoopType.SYNC,
    )
    gui.render(App, container)

    assert container["children"][0]["type"] == "widget"

    item = container["children"][0]["children"][0]
    assert item["type"] == "item"
    assert item["attrs"]["val"] == "foo", item["attrs"]
