from observ import reactive
import pytest

from kolla import EventLoopType, Kolla
from kolla.renderers import DictRenderer


@pytest.mark.xfail
def test_dynamic_attribute_prop(parse_source):
    App, _ = parse_source(
        """
        <app :foo="bar" />

        <script>
        bar = "baz"
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


@pytest.mark.xfail
def test_dynamic_attribute_value(parse_source):
    App, _ = parse_source(
        """
        <app :foo="420" />
        """
    )

    container = {"type": "root"}
    gui = Kolla(
        renderer=DictRenderer(),
        event_loop_type=EventLoopType.SYNC,
    )
    gui.render(App, container)

    app = container["children"][0]
    assert app["attrs"]["foo"] == 420


@pytest.mark.xfail
def test_dynamic_attribute_function(parse_source):
    App, _ = parse_source(
        """
        <app v-bind:foo="bar()" />

        <script>
        def bar():
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


@pytest.mark.xfail
def test_dynamic_attribute_undefined_prop(parse_source):
    with pytest.raises(Exception):
        parse_source(
            """
            <app :foo="bar" />

            <!--
             bar is not defined, so even when bar
             is passed in as a prop, it should result
             in an error during compilation already
            -->
            """
        )


@pytest.mark.xfail
def test_dynamic_attribute_props_change(parse_source):
    App, _ = parse_source(
        """
        <app :foo="bar" />

        <script>
        bar = "bla"
        </script>
        """
    )

    # state = reactive({"bar": "baz"})
    state = reactive({})
    container = {"type": "root"}
    gui = Kolla(
        renderer=DictRenderer(),
        event_loop_type=EventLoopType.SYNC,
    )
    gui.render(App, container, state=state)
    app = container["children"][0]

    assert app["attrs"]["foo"] == "bla"

    state["bar"] = "baz"

    assert app["attrs"]["foo"] == "baz"

    state["bar"] = "bam"

    assert app["attrs"]["foo"] == "bam"


@pytest.mark.xfail
def test_dynamic_attribute_object(parse_source):
    App, _ = parse_source(
        """
        <app v-bind="values" />

        <script>
        values = {}
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
