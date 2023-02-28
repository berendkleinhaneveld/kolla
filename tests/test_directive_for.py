import pytest
from observ import reactive

from kolla import EventLoopType, Kolla
from kolla.renderers import DictRenderer


@pytest.mark.xfail
def test_for_simple(parse_source):
    """Render a node with a 1_000 children.
    This test makes sure that `kolla` will not trigger a RecursionError.
    """
    number_of_items = 1_000
    App, _ = parse_source(
        f"""
        <node
          v-for="i in range({number_of_items})"
          :value="i"
        />
        """
    )

    container = {"type": "root"}
    gui = Kolla(
        renderer=DictRenderer(),
        event_loop_type=EventLoopType.SYNC,
    )
    gui.render(App, container)

    assert len(container["children"]) == number_of_items, container
    for idx, child in enumerate(container["children"]):
        assert child["attrs"]["value"] == idx


@pytest.mark.xfail
def test_for_with_children(parse_source):
    App, _ = parse_source(
        """
        <node
          v-for="i, text in enumerate(values)"
          :value="i"
        >
          <item :text="text" />
        </node>

        <script>
        values = []
        </script>
        """
    )

    state = {"values": ["a", "b", "c"]}
    container = {"type": "root"}
    gui = Kolla(
        renderer=DictRenderer(),
        event_loop_type=EventLoopType.SYNC,
    )
    gui.render(App, container, state=state)

    assert len(container["children"]) == len(state["values"]), container
    for idx, child in enumerate(container["children"]):
        assert child["attrs"]["value"] == idx
        assert child["children"][0]["attrs"]["text"] == state["values"][idx]


@pytest.mark.xfail
def test_for_between_other_tags(parse_source):
    App, _ = parse_source(
        """
        <foo />
        <node
          v-for="i in range(count)"
          :value="i"
        />
        <bar />

        <script>
        count = 0
        </script>
        """
    )

    container = {"type": "root"}
    state = reactive({"count": 10})
    gui = Kolla(
        renderer=DictRenderer(),
        event_loop_type=EventLoopType.SYNC,
    )
    gui.render(App, container, state=state)

    assert len(container["children"]) == 12
    assert container["children"][0]["type"] == "foo"
    assert container["children"][-1]["type"] == "bar"

    state["count"] = 12

    assert len(container["children"]) == 14
    assert container["children"][0]["type"] == "foo"
    assert container["children"][-1]["type"] == "bar"

    state["count"] = 4

    assert len(container["children"]) == 6
    assert container["children"][0]["type"] == "foo"
    assert container["children"][-1]["type"] == "bar"


@pytest.mark.xfail
def test_for_between_if_tags(parse_source):
    App, _ = parse_source(
        """
        <foo v-if="foo" />
        <node
          v-for="i in range(count)"
          :value="i"
        />
        <bar v-if="bar" />

        <script>
        foo = bar = True
        count = 0
        </script>
        """
    )

    state = reactive(
        {
            "foo": False,
            "bar": False,
            "count": 10,
        }
    )
    container = {"type": "root"}
    gui = Kolla(
        renderer=DictRenderer(),
        event_loop_type=EventLoopType.SYNC,
    )
    gui.render(App, container, state=state)

    assert len(container["children"]) == 10
    for idx, child in enumerate(container["children"]):
        assert child["attrs"]["value"] == idx

    state["foo"] = True

    assert len(container["children"]) == 11
    assert container["children"][0]["type"] == "foo"

    state["bar"] = True

    assert len(container["children"]) == 12
    assert container["children"][0]["type"] == "foo"
    assert container["children"][11]["type"] == "bar"


@pytest.mark.xfail
def test_for_reactive(parse_source):
    App, _ = parse_source(
        """
        <node
          v-for="i in items"
          :value="i"
        />

        <script>
        items = []
        </script>
        """
    )

    state = reactive({"items": ["a", "b"]})
    container = {"type": "root"}
    gui = Kolla(
        renderer=DictRenderer(),
        event_loop_type=EventLoopType.SYNC,
    )
    gui.render(App, container, state=state)

    assert len(container["children"]) == len(state["items"])
    for idx, item in enumerate(state["items"]):
        assert container["children"][idx]["attrs"]["value"] == item

    state["items"].append("c")

    assert len(container["children"]) == len(state["items"])
    for idx, item in enumerate(state["items"]):
        assert container["children"][idx]["attrs"]["value"] == item


@pytest.mark.xfail
def test_for_keyed(parse_source):
    # TODO: rewrite test
    assert False

    App, _ = parse_source(
        """
        <node
          v-for="i in items"
          :key="i"
          :value="i"
        />

        <script>
        items = []
        </script>
        """
    )

    state = reactive({"items": ["a", "b"]})
    container = {"type": "root"}
    gui = Kolla(
        renderer=DictRenderer(),
        event_loop_type=EventLoopType.SYNC,
    )
    gui.render(App, container, state=state)

    assert len(container["children"]) == len(state["items"])
    for idx, item in enumerate(state["items"]):
        assert container["children"][idx]["attrs"]["value"] == item

    state["items"].append("c")

    assert len(container["children"]) == len(state["items"])
    for idx, item in enumerate(state["items"]):
        assert container["children"][idx]["attrs"]["value"] == item
