from kolla import EventLoopType, Kolla
from kolla.renderers import DictRenderer
from kolla.renderers.dict_renderer import format_dict


def test_cgx_slots_named_fallback():
    from tests.data.slots.template_empty import Template

    gui = Kolla(DictRenderer(), event_loop_type=EventLoopType.SYNC)
    container = {"type": "root"}
    gui.render(Template, container)

    container = container["children"][0]
    assert container["type"] == "widget"

    header, content, footer = container["children"]

    assert header["type"] == "header"
    assert header["children"][0]["type"] == "label"
    assert header["children"][0]["attrs"]["text"] == "header fallback"

    assert content["type"] == "content"
    assert content["children"][0]["type"] == "label"
    assert content["children"][0]["attrs"]["text"] == "content fallback"
    assert len(content["children"]) == 1

    assert footer["type"] == "footer"
    assert footer["children"][0]["type"] == "label"
    assert footer["children"][0]["attrs"]["text"] == "footer fallback"


def test_cgx_slots_named_filled():
    from tests.data.slots.template import Template

    gui = Kolla(DictRenderer(), event_loop_type=EventLoopType.SYNC)
    container = {"type": "root"}
    gui.render(Template, container)

    container = container["children"][0]
    assert container["type"] == "widget"

    header, content, footer = container["children"]

    assert header["type"] == "header"
    assert "children" in header, format_dict(container)
    assert header["children"][0]["type"] == "label"
    assert header["children"][0]["attrs"]["text"] == "header content"

    assert content["type"] == "content"
    assert content["children"][0]["type"] == "label"
    assert content["children"][0]["attrs"]["text"] == "content"
    assert content["children"][1]["attrs"]["text"] == "even more content"
    assert len(content["children"]) == 2

    assert footer["type"] == "footer"
    assert footer["children"][0]["type"] == "label"
    assert footer["children"][0]["attrs"]["text"] == "footer content"


def test_cgx_slots_partial_no_fallback():
    from tests.data.slots.template_partial import Template

    gui = Kolla(DictRenderer(), event_loop_type=EventLoopType.SYNC)
    container = {"type": "root"}
    gui.render(Template, container)

    container = container["children"][0]
    assert container["type"] == "widget"

    header, content, footer = container["children"]

    assert header["type"] == "header"
    assert header["children"][0]["type"] == "label"
    assert header["children"][0]["attrs"]["text"] == "header content"

    assert content["type"] == "content"
    assert "children" not in content

    assert footer["type"] == "footer"
    assert footer["children"][0]["type"] == "label"
    assert footer["children"][0]["attrs"]["text"] == "footer content"


def test_cgx_slots_implicit_default_slot_name():
    from tests.data.slots.template_implicit_default_slot_name import Template

    gui = Kolla(DictRenderer(), event_loop_type=EventLoopType.SYNC)
    container = {"type": "root"}
    gui.render(Template, container)

    container = container["children"][0]
    assert container["type"] == "widget"

    header, content, footer = container["children"]

    assert header["type"] == "header"
    assert header["children"][0]["type"] == "label"
    assert header["children"][0]["attrs"]["text"] == "header content"

    assert content["type"] == "content"
    assert content["children"][0]["type"] == "label"
    assert content["children"][0]["attrs"]["text"] == "content"
    assert content["children"][1]["attrs"]["text"] == "even more content"
    assert len(content["children"]) == 2

    assert footer["type"] == "footer"
    assert footer["children"][0]["type"] == "label"
    assert footer["children"][0]["attrs"]["text"] == "footer content"


def test_cgx_slots_implicit_default_slot():
    from tests.data.slots.template_implicit_default_slot import Template

    gui = Kolla(DictRenderer(), event_loop_type=EventLoopType.SYNC)
    container = {"type": "root"}
    gui.render(Template, container)

    container = container["children"][0]
    assert container["type"] == "widget"

    header, content, footer = container["children"]

    assert header["type"] == "header"
    assert header["children"][0]["type"] == "label"
    assert header["children"][0]["attrs"]["text"] == "header content"

    assert content["type"] == "content"
    assert content["children"][0]["type"] == "label"
    assert content["children"][0]["attrs"]["text"] == "content"
    assert content["children"][1]["attrs"]["text"] == "even more content"
    assert len(content["children"]) == 2

    assert footer["type"] == "footer"
    assert footer["children"][0]["type"] == "label"
    assert footer["children"][0]["attrs"]["text"] == "footer content"


def test_cgx_slots_tree():
    from tests.data.slots.tree import Tree

    gui = Kolla(DictRenderer(), event_loop_type=EventLoopType.SYNC)
    container = {"type": "container"}
    gui.render(Tree, container)

    container = container["children"][0]
    assert container["type"] == "root"

    a, c = container["children"]

    assert a["type"] == "node"
    assert a["attrs"]["name"] == "a"

    assert c["type"] == "node"
    assert c["attrs"]["name"] == "c"

    assert a["children"][0]["type"] == "node"
    assert a["children"][0]["attrs"]["name"] == "b"


def test_cgx_slots_simple_tree():
    from tests.data.slots.simple_tree import Tree

    gui = Kolla(DictRenderer(), event_loop_type=EventLoopType.SYNC)
    container = {"type": "container"}
    gui.render(Tree, container)

    node = container["children"][0]
    assert node["type"] == "node"

    assert "children" in node, format_dict(container)
    content = node["children"][0]

    assert content["type"] == "content"

    # TODO:
    """
    NTS: I think that the solution to slots should be compatible with the way
    conditional directives are implemented. That means that the solution lies
    somewhere in the fragment.py Fragment::create|mount methods. But maybe
    it will require some code in the node parsing system to introduce 'fake'
    template nodes that surround unnamed root nodes, in order to group them
    into one 'default'-named template node. This might make the code within
    fragment.py easier to reason about.
    """


def test_cgx_slots_dynamic():
    # TODO: write test that dynamically adds/removes
    # slot content (v-if, v-for)
    pass
