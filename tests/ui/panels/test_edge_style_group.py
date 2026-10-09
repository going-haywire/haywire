"""One style edit reaches every selected edge that shares the active edge's style class."""

from types import SimpleNamespace

import pytest

from haybale_graph_editor.panels._edge_style import _fan_out_to, selection_shares_style, style_group
from haybale_graph_editor.state.edit_state import EditState
from haywire.core.graph.base import BaseGraph
from haywire.core.graph.scheduler import SyncScheduler

from tests.conftest import make_edge, make_node

pytestmark = pytest.mark.integration

_ADD = "haybale-testing:node:TestAddFloatNode"


@pytest.fixture
def graph(library_system) -> BaseGraph:
    return BaseGraph(filestem="Edge Style Group", validation_scheduler=SyncScheduler())


def _styled_edge(graph):
    from haybale_testing.nodes.testbed.visual_probe import VisualProbeNode

    key = VisualProbeNode.class_identity.registry_key
    source = make_node(graph, key, position=(0, 0))
    sink = make_node(graph, key, position=(300, 0))
    edge = make_edge(graph, source.node_id, "note_out", sink.node_id, "note_in")
    graph.force_validation()
    return edge


def _computed_edge(graph):
    a = make_node(graph, _ADD, position=(0, 0))
    b = make_node(graph, _ADD, position=(300, 0))
    edge = make_edge(graph, a.node_id, "result", b.node_id, "value_a")
    graph.force_validation()
    return edge


def _ctx(graph, active, selected, nodes=()):
    state = SimpleNamespace(
        active_edge=active,
        active_graph=graph,
        selected_edges={e.edge_id for e in selected},
        selected_nodes=set(nodes),
    )
    return SimpleNamespace(data={EditState: state})


def test_selected_edges_of_one_style_class_form_one_group(graph):
    first, second = _styled_edge(graph), _styled_edge(graph)
    ctx = _ctx(graph, first, [first, second])
    assert style_group(ctx) == [first, second] or style_group(ctx) == [first, second][::-1]
    assert style_group(ctx)[0] is first
    assert selection_shares_style(ctx)


def test_an_unselected_active_edge_is_its_own_group(graph):
    first, second = _styled_edge(graph), _styled_edge(graph)
    ctx = _ctx(graph, first, [second])
    assert style_group(ctx) == [first]


def test_a_selection_with_an_unstyled_edge_is_not_shared(graph):
    first, computed = _styled_edge(graph), _computed_edge(graph)
    ctx = _ctx(graph, first, [first, computed])
    assert style_group(ctx) == [first]
    assert not selection_shares_style(ctx)


def test_a_selection_with_a_node_is_not_shared(graph):
    first, second = _styled_edge(graph), _styled_edge(graph)
    ctx = _ctx(graph, first, [first, second], nodes=["some-node"])
    assert not selection_shares_style(ctx)


def test_an_edge_without_style_has_no_group(graph):
    computed = _computed_edge(graph)
    assert style_group(_ctx(graph, computed, [computed])) == []


def test_a_change_on_the_lead_is_written_to_the_peers(graph):
    lead, peer = _styled_edge(graph).style, _styled_edge(graph).style
    lead._subscribe(_fan_out_to(lead, [peer]))
    lead.color = "#ff0000"
    assert peer.color == "#ff0000"
    lead.width = 4.0
    assert peer.width == 4.0


def test_a_reset_on_the_lead_resets_the_peers(graph):
    lead, peer = _styled_edge(graph).style, _styled_edge(graph).style
    lead.color = "#ff0000"
    peer.color = "#00ff00"
    lead._subscribe(_fan_out_to(lead, [peer]))
    lead._reset("color")
    assert not peer._is_locally_set("color")
