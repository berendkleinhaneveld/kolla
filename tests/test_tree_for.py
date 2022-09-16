import pytest

from kolla import Kolla, EventLoopType
from kolla.renderers import DictRenderer


@pytest.mark.xfail
def test_for_simple(parse_source):
    """Render a node with a 1000 children.

    When using a recursive strategy to process fibers, this will result in a
    stack of 1000 calls to `commit_work` which triggers a RecursionError.
    This test makes sure that `kolla` will not trigger any RecursionError.
    """
    App, _ = parse_source(
        """
        <node
          v-for="i in range(10)"
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

    assert len(container["children"]) == 10
    for idx, child in enumerate(container["children"]):
        assert child["attrs"]["value"] == idx


@pytest.mark.xfail
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

    assert len(container["children"]) == 10
    for idx, child in enumerate(container["children"]):
        assert child["attrs"]["value"] == idx


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
    """Render a node with a 1000 children.

    When using a recursive strategy to process fibers, this will result in a
    stack of 1000 calls to `commit_work` which triggers a RecursionError.
    This test makes sure that `kolla` will not trigger any RecursionError.
    """
    App, _ = parse_source(
        """
        <app>
          <node
            v-for="_ in range(1000)"
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


@pytest.mark.xfail
def test_lots_of_elements(parse_source):
    """Render a node with a 1000 children.

    When using a recursive strategy to process fibers, this will result in a
    stack of 1000 calls to `commit_work` which triggers a RecursionError.
    This test makes sure that `kolla` will not trigger any RecursionError.
    """
    App, _ = parse_source(
        """
        <app>
          <node
            v-for="_ in range(1000)"
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
