from observ import reactive
import pytest

from kolla import Kolla, EventLoopType
from kolla.renderers import DictRenderer


def test_dynamic_attribute_object_method(parse_source):
    App, _ = parse_source(
        """
        <app v-bind:foo="bar()" />

        <script>
        import kolla

        class App(kolla.Component):
            def bar(self):
                return "baz"
        </script>
        """
    )

    container = {"type": "root"}
    gui = Kolla(
        renderer=DictRenderer(),
        event_loop_type=EventLoopType.SYNC,
    )
    gui.render(App, container)

    app = container["children"][0]
    assert app["attrs"]["foo"] == "baz"


def test_dynamic_attribute_object_property(parse_source):
    App, _ = parse_source(
        """
        <app :foo="bar" />

        <script>
        import kolla

        class App(kolla.Component):
            def __init__(self, props):
                super().__init__(props)
                self.bar = "baz"
        </script>
        """
    )

    container = {"type": "root"}
    gui = Kolla(
        renderer=DictRenderer(),
        event_loop_type=EventLoopType.SYNC,
    )
    gui.render(App, container)

    app = container["children"][0]
    assert app["attrs"]["foo"] == "baz"


def test_dynamic_attribute_module_scope(parse_source):
    App, _ = parse_source(
        """
        <app :foo="bar" />

        <script>
        import kolla

        bar = "baz"

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

    app = container["children"][0]
    assert app["attrs"]["foo"] == "baz"


def test_dynamic_attribute_state(parse_source):
    App, _ = parse_source(
        """
        <app :foo="bar" />

        <script>
        import kolla

        class App(kolla.Component):
            def __init__(self, props):
                super().__init__(props)
                self.state["bar"] = "baz"
        </script>
        """
    )

    container = {"type": "root"}
    gui = Kolla(
        renderer=DictRenderer(),
        event_loop_type=EventLoopType.SYNC,
    )
    gui.render(App, container)

    app = container["children"][0]
    assert app["attrs"]["foo"] == "baz"


def test_dynamic_attribute_props(parse_source):
    App, _ = parse_source(
        """
        <app :foo="bar" />

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
    gui.render(App, container, state={"bar": "baz"})

    app = container["children"][0]
    assert app["attrs"]["foo"] == "baz"


def test_dynamic_attribute_props_change(parse_source):
    App, _ = parse_source(
        """
        <app :foo="bar" />

        <script>
        import kolla

        class App(kolla.Component):
            pass
        </script>
        """
    )

    state = reactive({"bar": "baz"})
    container = {"type": "root"}
    gui = Kolla(
        renderer=DictRenderer(),
        event_loop_type=EventLoopType.SYNC,
    )
    gui.render(App, container, state=state)

    app = container["children"][0]
    assert app["attrs"]["foo"] == "baz"

    state["bar"] = "bam"

    assert app["attrs"]["foo"] == "bam"


@pytest.mark.xfail
def test_dynamic_attribute_object(parse_source):
    App, _ = parse_source(
        """
        <app v-bind="values" />

        <script>
        import kolla

        class App(kolla.Component):
            pass
        </script>
        """
    )

    state = reactive({"values": {"foo": "foo"}})
    container = {"type": "root"}
    gui = Kolla(
        renderer=DictRenderer(),
        event_loop_type=EventLoopType.SYNC,
    )
    gui.render(App, container, state=state)

    app = container["children"][0]
    assert app["attrs"]["foo"] == "foo"

    state["values"]["bar"] = "bar"

    assert app["attrs"]["foo"] == "foo"
    assert app["attrs"]["bar"] == "bar"

    state["values"]["bar"] = "baz"

    assert app["attrs"]["bar"] == "baz"
