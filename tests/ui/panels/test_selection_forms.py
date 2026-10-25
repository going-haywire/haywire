"""What a selection-wide form edits: hidden across kinds, greyed if non-uniform, own bag or neutral form."""

from types import SimpleNamespace

import pytest

from haybale_graph_editor.panels._selection_forms import (
    edge_style_subject,
    fan_out_to,
    node_appearance_subject,
)
from haybale_graph_editor.state.edit_state import EditState
from haywire.core.access import LevelMode
from haywire.core.graph.base import BaseGraph
from haywire.core.graph.edit_route import EditRoute
from haywire.core.graph.editor import Editor
from haywire.core.graph.scheduler import SyncScheduler
from haywire.core.graph.types import ChangeReason
from haywire.core.node.properties import NodeProperties
from haywire.core.types.enums import NodeDetail
from haywire.core.undo.config import UndoConfig

from tests.conftest import edit_route, make_edge, make_node

pytestmark = pytest.mark.integration

_ADD = "haybale-testing:node:TestAddFloatNode"


@pytest.fixture
def graph(library_system) -> BaseGraph:
    return BaseGraph(filestem="Selection Forms", validation_scheduler=SyncScheduler())


def _probe_key() -> str:
    from haybale_testing.nodes.testbed.visual_probe import VisualProbeNode

    return VisualProbeNode.class_identity.registry_key


def _styled_edge(graph):
    source = make_node(graph, _probe_key(), position=(0, 0))
    sink = make_node(graph, _probe_key(), position=(300, 0))
    edge = make_edge(graph, source.node_id, "note_out", sink.node_id, "note_in")
    graph.force_validation()
    return edge


def _computed_edge(graph):
    a = make_node(graph, _ADD, position=(0, 0))
    b = make_node(graph, _ADD, position=(300, 0))
    edge = make_edge(graph, a.node_id, "result", b.node_id, "value_a")
    graph.force_validation()
    return edge


def _ctx(graph, nodes=(), edges=(), routed=True):
    state = SimpleNamespace(
        active_graph=graph,
        active_route=edit_route(None) if routed else None,
        selected_nodes={n.node_id for n in nodes},
        selected_edges={e.edge_id for e in edges},
    )
    return SimpleNamespace(data={EditState: state})


# ---------------------------------------------------------------------------
# Edge Style
# ---------------------------------------------------------------------------


def test_one_styled_edge_edits_its_own_bag(graph):
    edge = _styled_edge(graph)
    subject = edge_style_subject(_ctx(graph, edges=[edge]))
    assert subject.status == "own"
    assert subject.bags == [edge.style]


def test_several_styled_edges_get_a_neutral_form(graph):
    first, second = _styled_edge(graph), _styled_edge(graph)
    subject = edge_style_subject(_ctx(graph, edges=[first, second]))
    assert subject.status == "neutral"
    assert subject.bag_class is type(first.style)
    assert {id(b) for b in subject.bags} == {id(first.style), id(second.style)}


def test_an_unstyled_edge_among_styled_ones_greys_with_a_reason(graph):
    subject = edge_style_subject(_ctx(graph, edges=[_styled_edge(graph), _computed_edge(graph)]))
    assert subject.status == "greyed"
    assert subject.reason == "Some selected edges have no style"


def test_only_unstyled_edges_hide_it(graph):
    assert edge_style_subject(_ctx(graph, edges=[_computed_edge(graph)])).status == "hidden"


def test_nodes_and_edges_together_hide_style(graph):
    edge = _styled_edge(graph)
    node = make_node(graph, _ADD, position=(0, 300))
    assert edge_style_subject(_ctx(graph, nodes=[node], edges=[edge])).status == "hidden"


# ---------------------------------------------------------------------------
# Node Appearance
# ---------------------------------------------------------------------------


def test_one_node_edits_its_own_props(graph):
    node = make_node(graph, _ADD, position=(0, 0))
    subject = node_appearance_subject(_ctx(graph, nodes=[node]))
    assert subject.status == "own"
    assert subject.bags == [node.node.props]


def test_several_nodes_get_a_neutral_form(graph):
    nodes = [make_node(graph, _ADD, position=(0, 0)), make_node(graph, _ADD, position=(300, 0))]
    subject = node_appearance_subject(_ctx(graph, nodes=nodes))
    assert subject.status == "neutral"
    assert subject.bag_class is not None
    assert issubclass(subject.bag_class, NodeProperties)


def test_a_reroute_among_the_nodes_greys_with_a_reason(graph):
    from haywire.barn.builtin.nodes.reroute import RerouteNode

    node = make_node(graph, _ADD, position=(0, 0))
    reroute = make_node(graph, RerouteNode.class_identity.registry_key, position=(300, 0))
    subject = node_appearance_subject(_ctx(graph, nodes=[node, reroute]))
    assert subject.status == "greyed"
    assert subject.reason == "Selection contains reroute nodes"


def test_nodes_and_edges_together_hide_appearance(graph):
    edge = _styled_edge(graph)
    node = make_node(graph, _ADD, position=(0, 300))
    assert node_appearance_subject(_ctx(graph, nodes=[node], edges=[edge])).status == "hidden"


# ---------------------------------------------------------------------------
# The neutral form's fan-out
# ---------------------------------------------------------------------------


@pytest.fixture
def route(graph, library_system) -> EditRoute:
    return edit_route(Editor(graph, library_system.get_node_factory()))


def _neutral(bag_class, bags, route, graph=None):
    from haywire.core.di.context import get_settings_registry

    neutral = bag_class(registry=get_settings_registry())
    if graph is not None:
        neutral._graph = graph
    neutral._subscribe_settings()
    neutral._subscribe(fan_out_to(neutral, bags, route))
    return neutral


def test_a_change_on_the_neutral_form_is_set_on_every_edge(graph, route):
    first, second = _styled_edge(graph), _styled_edge(graph)
    neutral = _neutral(type(first.style), [first.style, second.style], route)
    neutral.color = "#ff0000"
    assert first.style.color == "#ff0000"
    assert second.style.color == "#ff0000"


def test_a_reset_on_the_neutral_form_resets_every_edge(graph, route):
    first, second = _styled_edge(graph), _styled_edge(graph)
    neutral = _neutral(type(first.style), [first.style, second.style], route)
    neutral.color = "#ff0000"
    neutral._reset("color")
    assert not first.style._is_locally_set("color")
    assert not second.style._is_locally_set("color")


def test_the_neutral_node_form_shows_the_graphs_value(graph, route):
    graph.props.detail = NodeDetail.PINS_ALL.value
    nodes = [make_node(graph, _ADD, position=(0, 0)), make_node(graph, _ADD, position=(300, 0))]
    neutral = _neutral(NodeProperties, [n.node.props for n in nodes], route, graph=graph)
    assert neutral.detail == NodeDetail.PINS_ALL.value


def test_a_graph_change_reaching_the_neutral_form_leaves_the_nodes_alone(graph, route):
    nodes = [make_node(graph, _ADD, position=(0, 0)), make_node(graph, _ADD, position=(300, 0))]
    nodes[0].node.props.detail = NodeDetail.PINS_ALL.value  # a local override the graph must not clear
    _neutral(NodeProperties, [n.node.props for n in nodes], route, graph=graph)
    graph.props.detail = NodeDetail.LABELS.value
    assert nodes[0].node.props._is_locally_set("detail")
    assert nodes[0].node.props.detail == NodeDetail.PINS_ALL.value


def test_a_neutral_change_marks_every_node(graph, route):
    nodes = [make_node(graph, _ADD, position=(0, 0)), make_node(graph, _ADD, position=(300, 0))]
    graph.force_validation()
    neutral = _neutral(NodeProperties, [n.node.props for n in nodes], route, graph=graph)
    seen: list = []
    graph.subscribe_to_validation(seen.append)

    neutral.detail = NodeDetail.PINS_ALL.value

    marked = {node_id: reason for result in seen for node_id, reason in result.nodes.items()}
    assert marked == {n.node_id: ChangeReason.NODE_VALUE_CHANGED for n in nodes}
    assert all(n.node.props.detail == NodeDetail.PINS_ALL.value for n in nodes)


def test_a_form_edit_is_one_undo_step(graph, library_system):
    config = UndoConfig(enable_auto_grouping=False, enable_action_merging=True)
    editor = Editor(graph, library_system.get_node_factory(), undo_config=config)
    route = edit_route(editor)
    nodes = [make_node(graph, _ADD, position=(i * 300, 0)) for i in range(3)]
    graph.force_validation()
    bags = [n.node.props for n in nodes]
    bags[1].detail = NodeDetail.WIDGETS.value  # one bag starts with its own value
    neutral = _neutral(NodeProperties, bags, route, graph=graph)

    neutral.detail = NodeDetail.PINS_ALL.value
    neutral.detail = NodeDetail.LABELS.value  # same field, within 3 s: amends

    assert all(b.detail == NodeDetail.LABELS.value for b in bags)
    assert editor.undo() is True
    # one undo restores every bag to its own first old value
    assert bags[1].detail == NodeDetail.WIDGETS.value
    assert not bags[0]._is_locally_set("detail")
    assert not bags[2]._is_locally_set("detail")
    assert editor.can_undo() is False
    # redo replays the amended (latest) value on every bag
    assert editor.redo() is True
    assert all(b.detail == NodeDetail.LABELS.value for b in bags)


def test_a_refused_neutral_change_reaches_no_bag(graph, library_system):
    route = edit_route(Editor(graph, library_system.get_node_factory()), LevelMode.OPERATE)
    first, second = _styled_edge(graph), _styled_edge(graph)
    neutral = _neutral(type(first.style), [first.style, second.style], route)

    assert route.set_setting(neutral, "color", "#ff0000", minimum=LevelMode.EDIT) is False
    neutral.color = "#00ff00"  # a neutral write that skipped the route still reaches no bag

    assert not first.style._is_locally_set("color")
    assert not second.style._is_locally_set("color")


# ---------------------------------------------------------------------------
# No route: a graph-document bag is never drawn writable
# ---------------------------------------------------------------------------


def test_without_a_route_both_forms_are_hidden(graph):
    edge = _styled_edge(graph)
    node = make_node(graph, _ADD, position=(0, 300))
    assert edge_style_subject(_ctx(graph, edges=[edge], routed=False)).status == "hidden"
    assert node_appearance_subject(_ctx(graph, nodes=[node], routed=False)).status == "hidden"


def test_an_own_form_without_a_route_draws_no_row(graph, monkeypatch):
    from unittest.mock import MagicMock

    from haybale_graph_editor.panels import _selection_forms as forms

    drawn = MagicMock()
    monkeypatch.setattr(forms, "render_settings", drawn)
    edge = _styled_edge(graph)
    subject = edge_style_subject(_ctx(graph, edges=[edge]))
    assert subject.status == "own"
    forms.render_form(_ctx(graph, edges=[edge], routed=False), subject)
    drawn.assert_not_called()


def test_a_graph_panel_without_a_route_draws_no_row(graph, monkeypatch):
    from unittest.mock import MagicMock

    from haybale_graph_editor.panels.properties.setting import graph as graph_panel

    drawn = MagicMock()
    monkeypatch.setattr(graph_panel, "route_for", lambda ctx: None)
    monkeypatch.setattr(graph_panel, "render_settings", drawn)
    ctx = SimpleNamespace(data={EditState: SimpleNamespace(active_graph=graph)})
    graph_panel.GraphSettingsPanel.draw(MagicMock(), ctx, MagicMock())  # type: ignore[arg-type]
    drawn.assert_not_called()
