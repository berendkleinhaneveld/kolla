import pytest

from kolla import Kolla, EventLoopType
from kolla.renderers import DictRenderer


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

    assert len(container["children"]) == number_of_items, container
    for idx, child in enumerate(container["children"]):
        assert child["attrs"]["value"] == idx


def test_for_with_children(parse_source):
    values = ["a", "b", "c"]
    App, _ = parse_source(
        f"""
        <node
          v-for="i, text in enumerate({values})"
          :value="i"
        >
          <item :text="text" />
        </node>

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

    assert len(container["children"]) == len(values), container
    for idx, child in enumerate(container["children"]):
        assert child["attrs"]["value"] == idx
        assert child["children"][0]["attrs"]["text"] == values[idx]


def test_for_between_other_tags(parse_source):
    """Render a node with a 1000 children.

    When using a recursive strategy to process fibers, this will result in a
    stack of 1000 calls to `commit_work` which triggers a RecursionError.
    This test makes sure that `kolla` will not trigger any RecursionError.
    """
    App, _ = parse_source(
        """
        <foo />
        <node
          v-for="i in range(10)"
          :value="i"
        />
        <bar />

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

    assert len(container["children"]) == 12
    assert container["children"][0]["type"] == "foo"
    assert container["children"][-1]["type"] == "bar"

    # TODO: add tests for response to changes in size of v-for


@pytest.mark.xfail
def test_for_between_if_tags(parse_source):
    """Render a node with a 1000 children.

    When using a recursive strategy to process fibers, this will result in a
    stack of 1000 calls to `commit_work` which triggers a RecursionError.
    This test makes sure that `kolla` will not trigger any RecursionError.
    """
    App, _ = parse_source(
        """
        <foo v-if="foo" />
        <node
          v-for="i in range(10)"
          :value="i"
        />
        <bar v-if="bar" />

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

    assert len(container["children"]) == 10
    for idx, child in enumerate(container["children"]):
        assert child["attrs"]["value"] == idx


@pytest.mark.xfail
def test_for_keyed(parse_source):
    App, _ = parse_source(
        """
        <app>
          <node
            v-for="_ in range(1000)"
            :key="
          />
        </app>

        <script>
        import kolla

        class App(kolla.Component):
            pass
        </script>
        """
    )

    container = {"type": "root"}
    gui = Kolla(renderer=DictRenderer(), event_loop_type=EventLoopType.SYNC)
    gui.render(App, container)

    assert len(container["children"][0]["children"]) == 1000
