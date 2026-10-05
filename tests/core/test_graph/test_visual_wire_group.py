"""A VISUAL wire crosses a Group boundary like any other wire type (decision Q41)."""

import pytest

from haywire.core.graph.subgraph import SubgraphDefinition
from haywire.core.types import WireRole
from haywire.core.undo.actions.graph_actions import CollapseToGraphNodeAction

from tests.conftest import make_edge, make_node

pytestmark = pytest.mark.integration

_INPUT = "haywire-core:node:SubgraphInputNode"
_OUTPUT = "haywire-core:node:SubgraphOutputNode"
_CARD = "haywire-core:node:GraphNode"


def _probe_key():
    from haybale_testing.nodes.testbed.visual_probe import VisualProbeNode

    return VisualProbeNode.class_identity.registry_key


def _chain(graph):
    """outer_a → inner_a → inner_b → outer_b, every edge on the visual wire."""
    nodes = [make_node(graph, _probe_key(), position=(300 * i, 0)) for i in range(4)]
    for left, right in zip(nodes, nodes[1:], strict=False):
        make_edge(graph, left.node_id, "note_out", right.node_id, "note_in")
    graph.force_validation()
    return nodes


def _collapse(graph, node_ids):
    action = CollapseToGraphNodeAction(
        graph=graph,
        node_ids=list(node_ids),
        card_registry_key=_CARD,
        input_registry_key=_INPUT,
        output_registry_key=_OUTPUT,
        label="Group",
    )
    action.execute()
    return action


def _edges(graph):
    """Endpoint pairs of every edge, each with its wire role."""
    return {
        (e.source_node_id, e.sink_node_id): e.wire_type.role if e.wire_type is not None else None
        for e in graph.edge_wrappers.values()
    }


def _kinds(graph):
    return sorted(w.node.class_identity.registry_key for w in graph.node_wrappers.values())


def _assert_group_shape(graph, key, card_id, outer_a, outer_b, inner_a, inner_b):
    """The outer graph and the Group's interior carry the visual chain end to end."""
    assert _kinds(graph) == sorted([_probe_key(), _probe_key(), _CARD])
    assert card_id in graph.node_wrappers
    assert _edges(graph) == {
        (outer_a.node_id, card_id): WireRole.VISUAL,
        (card_id, outer_b.node_id): WireRole.VISUAL,
    }

    interior = graph.get_subgraph(key)
    assert interior is not None
    assert _kinds(interior) == sorted([_probe_key(), _probe_key(), _INPUT, _OUTPUT])
    by_key = {w.node.class_identity.registry_key: w.node_id for w in interior.node_wrappers.values()}
    boundary_in, boundary_out = by_key[_INPUT], by_key[_OUTPUT]
    assert _edges(interior) == {
        (boundary_in, inner_a.node_id): WireRole.VISUAL,
        (inner_a.node_id, inner_b.node_id): WireRole.VISUAL,
        (inner_b.node_id, boundary_out): WireRole.VISUAL,
    }
    assert all(e.state.is_valid() for e in interior.edge_wrappers.values())


def test_collapsing_across_a_visual_edge_keeps_every_edge_valid(graph_with_library_system):
    graph = graph_with_library_system
    outer_a, inner_a, inner_b, outer_b = _chain(graph)

    action = _collapse(graph, [inner_a.node_id, inner_b.node_id])
    graph.force_validation()

    assert all(w.is_valid() for w in graph.node_wrappers.values())
    assert all(e.state.is_valid() for e in graph.edge_wrappers.values())
    _assert_group_shape(graph, action.subgraph_key, action.card_node_id, outer_a, outer_b, inner_a, inner_b)

    data = graph.to_dict()
    graph.clear()
    graph.load_from_dict(data)
    graph.force_validation()
    assert all(e.state.is_valid() for e in graph.edge_wrappers.values())
    _assert_group_shape(graph, action.subgraph_key, action.card_node_id, outer_a, outer_b, inner_a, inner_b)


def test_undoing_the_collapse_restores_the_visual_chain(graph_with_library_system):
    graph = graph_with_library_system
    nodes = _chain(graph)
    before = {(e.source_node_id, e.sink_node_id) for e in graph.edge_wrappers.values()}

    action = _collapse(graph, [nodes[1].node_id, nodes[2].node_id])
    collapsed = {(e.source_node_id, e.sink_node_id) for e in graph.edge_wrappers.values()}
    assert nodes[1].node_id not in graph.node_wrappers
    assert nodes[2].node_id not in graph.node_wrappers
    assert action.card_node_id in graph.node_wrappers
    assert collapsed != before

    action.undo()
    graph.force_validation()

    after = {(e.source_node_id, e.sink_node_id) for e in graph.edge_wrappers.values()}
    assert after == before
    assert all(e.state.is_valid() for e in graph.edge_wrappers.values())


def test_a_visual_wire_grows_a_boundary_slot(graph_with_library_system):
    graph = graph_with_library_system
    definition = graph.add_subgraph(SubgraphDefinition(key="sg_visual", label="G"))
    output = make_node(definition, _OUTPUT)
    probe = make_node(definition, _probe_key())
    slot = next(p for p in output.node.ports.values() if p.id.startswith("slot_"))

    edge = definition.create_edge_wrapper(probe.node_id, "note_out", output.node_id, slot.id)
    definition.force_validation()

    assert edge is not None
    grown = output.node.ports[slot.id]
    assert grown.wire_type is not None and grown.wire_type.role is WireRole.VISUAL  # noqa: PT018
    assert edge.state.is_valid()
