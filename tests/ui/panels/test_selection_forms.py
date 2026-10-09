"""What a selection-wide form edits: hidden across kinds, greyed if non-uniform, own bag or neutral form."""

from types import SimpleNamespace

import pytest

from haybale_graph_editor.panels._selection_forms import (
    edge_style_subject,
    fan_out_to,
    node_appearance_subject,
)
from haybale_graph_editor.state.edit_state import EditState
from haywire.core.graph.base import BaseGraph
from haywire.core.graph.scheduler import SyncScheduler
from haywire.core.node.properties import NodeProperties
from haywire.core.types.enums import NodeDetail

from tests.conftest import make_edge, make_node

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


def _ctx(graph, nodes=(), edges=()):
    state = SimpleNamespace(
        active_graph=graph,
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


def _neutral(bag_class, bags, graph=None):
    from haywire.core.di.context import get_settings_registry

    neutral = bag_class(registry=get_settings_registry())
    if graph is not None:
        neutral._graph = graph
    neutral._subscribe_settings()
    neutral._subscribe(fan_out_to(neutral, bags))
    return neutral


def test_a_change_on_the_neutral_form_is_set_on_every_edge(graph):
    first, second = _styled_edge(graph), _styled_edge(graph)
    neutral = _neutral(type(first.style), [first.style, second.style])
    neutral.color = "#ff0000"
    assert first.style.color == "#ff0000"
    assert second.style.color == "#ff0000"


def test_a_reset_on_the_neutral_form_resets_every_edge(graph):
    first, second = _styled_edge(graph), _styled_edge(graph)
    neutral = _neutral(type(first.style), [first.style, second.style])
    neutral.color = "#ff0000"
    neutral._reset("color")
    assert not first.style._is_locally_set("color")
    assert not second.style._is_locally_set("color")


def test_the_neutral_node_form_shows_the_graphs_value(graph):
    graph.props.detail = NodeDetail.PINS_ALL.value
    nodes = [make_node(graph, _ADD, position=(0, 0)), make_node(graph, _ADD, position=(300, 0))]
    neutral = _neutral(NodeProperties, [n.node.props for n in nodes], graph=graph)
    assert neutral.detail == NodeDetail.PINS_ALL.value


def test_a_graph_change_reaching_the_neutral_form_leaves_the_nodes_alone(graph):
    nodes = [make_node(graph, _ADD, position=(0, 0)), make_node(graph, _ADD, position=(300, 0))]
    nodes[0].node.props.detail = NodeDetail.PINS_ALL.value  # a local override the graph must not clear
    _neutral(NodeProperties, [n.node.props for n in nodes], graph=graph)
    graph.props.detail = NodeDetail.LABELS.value
    assert nodes[0].node.props._is_locally_set("detail")
    assert nodes[0].node.props.detail == NodeDetail.PINS_ALL.value
