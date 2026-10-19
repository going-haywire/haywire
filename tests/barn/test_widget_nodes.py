"""The widget nodes: a control with a widget-less inlet and an outlet whose widget is the node.

Pins the inquisition's rules (5d, 2026-10-18): a linked value is forwarded and
an unlink keeps the last one (Q2 A, Q4 A); settings drive the widget's config
(Q6 B) through ``DataPort.set_widget_config``; a widget write on the outlet
reaches downstream at once (plan Decision 1); the saved value reaches
downstream when an edge links.
"""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from haybale_core.keys import WIDGET_NODE_SKIN
from haybale_core.nodes.widgets.menu import MenuNode
from haybale_core.nodes.widgets.number import FloatNumberNode, IntNumberNode
from haybale_core.nodes.widgets.slider import FloatSliderNode, IntSliderNode
from haybale_core.nodes.widgets.text import TextNode
from haybale_core.nodes.widgets.toggle import ToggleNode
from haywire.barn.builtin import widget_keys
from haywire.core.access import LevelMode
from haywire.core.graph.base import BaseGraph
from haywire.core.graph.edit_route import EditRoute
from haywire.core.graph.editor import Editor
from haywire.core.node.promotion import promote_setting
from haywire.core.skin.settings import _widget_node_stage_skin_choices
from haywire.core.types.enums import PortType, ShowWidgetStrategy
from haywire.core.undo.config import UndoConfig
from tests.conftest import make_node

pytestmark = pytest.mark.integration

_NODES: list[tuple[Any, str, Any]] = [
    (FloatSliderNode, widget_keys.SLIDER_WIDGET, 0.0),
    (IntSliderNode, widget_keys.SLIDER_WIDGET, 0),
    (FloatNumberNode, widget_keys.NUMBER_WIDGET, 0.0),
    (IntNumberNode, widget_keys.NUMBER_WIDGET, 0),
    (ToggleNode, widget_keys.SWITCH_WIDGET, False),
    (TextNode, widget_keys.TEXT_WIDGET, ""),
    (MenuNode, widget_keys.SELECT_WIDGET, "One"),
]


def _add(graph: BaseGraph, cls: Any, x: float = 0.0):
    wrapper = make_node(graph, cls.class_identity.registry_key, position=(x, 0))
    assert isinstance(wrapper.node, cls), "an unknown key yields an ErrorNode"
    return wrapper


def _link(graph: BaseGraph, src, src_port: str, sink, sink_port: str):
    edge = graph.create_edge_wrapper(src.node_id, src_port, sink.node_id, sink_port)
    assert edge is not None
    assert edge.state.is_valid()
    return edge


@pytest.mark.parametrize(("cls", "widget_key", "default"), _NODES)
def test_a_widget_node_has_a_hidden_inlet_and_a_shown_outlet(
    graph_with_library_system, cls, widget_key, default
):
    node = _add(graph_with_library_system, cls).node
    assert node.ports["in"].show_widget is ShowWidgetStrategy.NEVER
    assert node.ports["value"].show_widget is ShowWidgetStrategy.ALWAYS
    assert node.ports["value"].widget_key == widget_key
    assert node.ports["value"].get_value() == default


@pytest.mark.parametrize(("cls", "widget_key", "default"), _NODES)
def test_a_widget_node_binds_the_widget_node_stage_skin(graph_with_library_system, cls, widget_key, default):
    node = _add(graph_with_library_system, cls).node
    assert node.props.stage_skin == WIDGET_NODE_SKIN
    descriptor = type(node.props)._settings_descriptors()["stage_skin"]
    assert descriptor.widget_config["properties"]["options"] is _widget_node_stage_skin_choices


def _fed_slider(graph: BaseGraph):
    """A Float Number feeding a Float Slider feeding a Float Number sink."""
    source = _add(graph, FloatNumberNode, 0)
    slider = _add(graph, FloatSliderNode, 200)
    sink = _add(graph, FloatNumberNode, 400)
    edge = _link(graph, source, "value", slider, "in")
    _link(graph, slider, "value", sink, "in")
    return source, slider, sink, edge


def test_a_linked_value_is_forwarded(graph_with_library_system):
    source, slider, sink, _ = _fed_slider(graph_with_library_system)

    source.node.ports["value"].set_value(0.73)
    slider.node._execute(MagicMock())

    assert slider.node.ports["value"].get_value() == 0.73
    assert sink.node.ports["in"].get_value() == 0.73


def test_an_unlink_keeps_the_last_value(graph_with_library_system):
    graph = graph_with_library_system
    source, slider, sink, edge = _fed_slider(graph)
    source.node.ports["value"].set_value(0.73)
    slider.node._execute(MagicMock())

    graph.remove_edge_wrapper(edge.edge_id)
    slider.node._execute(MagicMock())

    assert slider.node.ports["value"].get_value() == 0.73
    assert sink.node.ports["in"].get_value() == 0.73


def _route(graph: BaseGraph, library_system, level: LevelMode) -> tuple[EditRoute, Editor]:
    config = UndoConfig(enable_auto_grouping=False, enable_action_merging=False)
    editor = Editor(graph, library_system.get_node_factory(), undo_config=config)
    return EditRoute(lambda: editor, lambda: level), editor


def test_a_widget_write_reaches_downstream_at_once(graph_with_library_system, library_system):
    graph = graph_with_library_system
    slider = _add(graph, FloatSliderNode, 0)
    sink = _add(graph, FloatNumberNode, 200)
    _link(graph, slider, "value", sink, "in")
    route, _ = _route(graph, library_system, LevelMode.OPERATE)

    assert route.set_port(slider.node_id, "value", 0.5, minimum=LevelMode.OPERATE) is True

    assert sink.node.ports["in"].get_value() == 0.5
    assert "in" in sink.node._has_dirty_ports
    assert sink.node.ports["value"].get_value() == 0.0, "the sink acts on it only when it runs"


def test_an_operator_write_is_not_an_undo_step(graph_with_library_system, library_system):
    graph = graph_with_library_system
    slider = _add(graph, FloatSliderNode)
    route, editor = _route(graph, library_system, LevelMode.OPERATE)
    route.set_port(slider.node_id, "value", 0.5, minimum=LevelMode.OPERATE)
    assert editor.can_undo() is False


def test_an_edit_write_is_one(graph_with_library_system, library_system):
    graph = graph_with_library_system
    slider = _add(graph, FloatSliderNode)
    route, editor = _route(graph, library_system, LevelMode.EDIT)
    route.set_port(slider.node_id, "value", 0.5, minimum=LevelMode.OPERATE)
    assert editor.can_undo() is True


def test_a_range_setting_reaches_the_widget_config(graph_with_library_system):
    node = _add(graph_with_library_system, FloatSliderNode).node
    node.range.max = 5.0
    assert node.ports["value"].widget_config["properties"]["max"] == 5.0


def test_a_number_without_bounds_has_no_min_or_max(graph_with_library_system):
    node = _add(graph_with_library_system, FloatNumberNode).node
    properties = node.ports["value"].widget_config["properties"]
    assert "min" not in properties
    assert "max" not in properties

    node.range.min = 1.0
    assert node.ports["value"].widget_config["properties"]["min"] == 1.0
    node.range.min = None
    assert "min" not in node.ports["value"].widget_config["properties"]


def test_a_driven_max_redraws_only_on_change(graph_with_library_system):
    graph = graph_with_library_system
    driver = _add(graph, FloatNumberNode, 0)
    slider = _add(graph, FloatSliderNode, 200)
    promote_setting(slider.node, "range", "max", direction=PortType.INLET)
    max_port = type(slider.node.range).__dict__["max"].storage_key
    _link(graph, driver, "value", slider, max_port)
    slider.node.ports["value"].set_value(7.0)

    with patch.object(slider, "redraw") as redraw:
        driver.node.ports["value"].set_value(5.0)
        assert redraw.call_count == 1
        driver.node.ports["value"].set_value(5.0)
        assert redraw.call_count == 1

    assert slider.node.ports["value"].widget_config["properties"]["max"] == 5.0
    assert slider.node.ports["value"].get_value() == 7.0, "nothing clamps the value"


def test_menu_options_reach_the_select(graph_with_library_system):
    node = _add(graph_with_library_system, MenuNode).node
    node.menu.options = ["A", "B"]
    assert node.ports["value"].widget_config["properties"]["options"] == ["A", "B"]
    assert node.ports["value"].get_value() == "One"


def test_text_commits(graph_with_library_system):
    node = _add(graph_with_library_system, TextNode).node
    assert node.ports["value"].widget_config["properties"]["commit"] is True


def test_a_saved_widget_node_round_trips(graph_with_library_system):
    graph = graph_with_library_system
    wrapper = _add(graph, IntSliderNode)
    wrapper.node.range.max = 10
    wrapper.node.ports["value"].set_value(7)

    data = graph.to_dict()
    graph.clear()
    graph.load_from_dict(data)

    node = graph.node_wrappers[wrapper.node_id].node
    assert node.range.max == 10
    assert node.ports["value"].widget_config["properties"]["max"] == 10
    assert node.ports["value"].get_value() == 7


def test_the_saved_value_reaches_downstream_on_link(graph_with_library_system):
    graph = graph_with_library_system
    number = _add(graph, IntNumberNode, 0)
    sink = _add(graph, IntNumberNode, 200)
    number.node.ports["value"].set_value(42)

    _link(graph, number, "value", sink, "in")
    graph._validation.force_immediate_validation()

    assert sink.node.ports["in"].get_value() == 42


def test_only_the_seven_widget_nodes_are_registered(library_system):
    names = library_system.get_node_registry().list_names()
    widget_nodes = sorted(name for name in names if name.startswith("haybale-core:node:") and "Node" in name)
    for cls, _, _ in _NODES:
        assert cls.class_identity.registry_key in names
    assert not any(name.endswith(":WidgetNode") for name in names), widget_nodes


# ---------------------------------------------------------------------------
# The style bag (slice 5d-3b)
# ---------------------------------------------------------------------------

_STYLE_DEFAULTS = {
    "label_position": "left",
    "max_label_width": None,
    "label_align": "left",
    "font": "sans",
    "font_size": 14,
    "bold": False,
    "italic": False,
    "label_color": "",
    "background": "",
    "border": False,
}


@pytest.mark.parametrize(("cls", "widget_key", "default"), _NODES)
def test_every_widget_node_has_the_style_bag(graph_with_library_system, cls, widget_key, default):
    from haywire.core.settings import Promotable, settings_fields

    node = _add(graph_with_library_system, cls).node
    fields = settings_fields(type(node.style))
    assert set(fields) == set(_STYLE_DEFAULTS)
    for name, value in _STYLE_DEFAULTS.items():
        assert getattr(node.style, name) == value, name
        assert fields[name]._promotable is Promotable.NONE, name


def test_a_default_widget_node_saves_no_style_values(graph_with_library_system):
    node = _add(graph_with_library_system, FloatSliderNode).node
    assert node._to_dict()["settings"]["style"]["values"] == {}


def test_a_style_change_redraws_and_undoes(graph_with_library_system, library_system):
    graph = graph_with_library_system
    wrapper = _add(graph, FloatSliderNode)
    route, editor = _route(graph, library_system, LevelMode.EDIT)

    with patch.object(wrapper, "redraw") as redraw:
        assert route.set_setting(wrapper.node.style, "bold", True, minimum=LevelMode.EDIT) is True
        assert redraw.call_count == 1

    assert wrapper.node.style.bold is True
    assert editor.undo()
    assert wrapper.node.style.bold is False
