"""Note links: any side to any side, one per pin pair, kept through collapse, paste and reroute."""

import json

import pytest

from tests.conftest import make_edge, make_node

pytestmark = pytest.mark.integration


@pytest.fixture
def graph(graph_with_library_system):
    return graph_with_library_system


def _key() -> str:
    from haywire.barn.builtin.nodes.annotation import AnnotationNode

    return AnnotationNode.class_identity.registry_key


def _notes(graph, count: int):
    return [make_node(graph, _key(), position=(400 * i, 0)) for i in range(count)]


def _links(graph):
    """Every edge as ``(source node, outlet port, sink node, inlet port)``."""
    return {
        (e.source_node_id, e.outlet_port_id, e.sink_node_id, e.inlet_port_id)
        for e in graph.edge_wrappers.values()
    }


def test_any_side_links_to_any_side(graph):
    from haywire.barn.builtin.types import ADD, ANNOTATION

    a, b = _notes(graph, 2)
    pairs = (("right_0", "top_0"), ("left_0", "left_0"), ("bottom_0", "right_0"))
    edges = [make_edge(graph, a.node_id, outlet, b.node_id, inlet) for outlet, inlet in pairs]
    graph.force_validation()

    assert all(edge.is_valid() for edge in edges)
    for wrapper, slots in ((a, ("right", "left", "bottom")), (b, ("top", "left", "right"))):
        assert wrapper.is_valid()
        assert wrapper.state.error_structural is None
        for side in slots:
            assert wrapper.node.ports[f"{side}_0"].type_cls is ANNOTATION
            assert wrapper.node.ports[f"{side}_1"].type_cls is ADD[ANNOTATION]


def test_a_reverse_note_link_is_refused(graph):
    a, b = _notes(graph, 2)
    link = make_edge(graph, a.node_id, "right_0", b.node_id, "left_0")
    graph.force_validation()
    assert link.is_valid()

    with pytest.raises(ValueError, match="other way"):
        graph.create_edge_wrapper(b.node_id, "left_0", a.node_id, "right_0")
    assert len(graph.edge_wrappers) == 1


def test_collapsing_across_note_links_keeps_them(graph):
    from haywire.barn.builtin.nodes.graph_node import GraphNode
    from haywire.barn.builtin.nodes.subgraph_io import SubgraphInputNode, SubgraphOutputNode
    from haywire.core.undo.actions.graph_actions import CollapseToGraphNodeAction

    first, middle, last = _notes(graph, 3)
    make_edge(graph, first.node_id, "right_0", middle.node_id, "left_0")
    make_edge(graph, middle.node_id, "right_0", last.node_id, "left_0")
    graph.force_validation()
    before = _links(graph)

    action = CollapseToGraphNodeAction(
        graph=graph,
        node_ids=[middle.node_id],
        card_registry_key=GraphNode.class_identity.registry_key,
        input_registry_key=SubgraphInputNode.class_identity.registry_key,
        output_registry_key=SubgraphOutputNode.class_identity.registry_key,
        label="Group",
    )
    action.execute()
    graph.force_validation()

    card = action.card_node_id
    assert {(e.source_node_id, e.sink_node_id) for e in graph.edge_wrappers.values()} == {
        (first.node_id, card),
        (card, last.node_id),
    }
    interior = graph.get_subgraph(action.subgraph_key)
    assert interior is not None
    # One edge arrives at the note's left pin, one leaves its right pin.
    assert sorted(
        e.inlet_port_id if e.sink_node_id == middle.node_id else e.outlet_port_id
        for e in interior.edge_wrappers.values()
    ) == ["left_0", "right_0"]
    for edges in (graph.edge_wrappers, interior.edge_wrappers):
        assert all(e.is_valid() for e in edges.values())

    action.undo()
    graph.force_validation()

    assert _links(graph) == before
    assert all(e.is_valid() for e in graph.edge_wrappers.values())


def test_pasting_two_linked_notes_keeps_their_link(graph):  # Review Focus 5
    from haywire.core.graph.clipboard import build_clipboard_payload
    from haywire.core.undo.actions.graph_actions import PasteClipboardAction

    a, b = _notes(graph, 2)
    original = make_edge(graph, a.node_id, "right_0", b.node_id, "left_0")
    graph.force_validation()

    copied = build_clipboard_payload(graph, [a.node_id, b.node_id], [original.edge_id], session_id="s")
    # The OS clipboard carries the payload as JSON text.
    payload = json.loads(json.dumps(copied))
    action = PasteClipboardAction(graph=graph, payload=payload, paste_x=900.0, paste_y=900.0)
    action.execute()
    graph.force_validation()

    pasted = set(action.new_node_ids)
    (copy,) = (e for e in graph.edge_wrappers.values() if {e.source_node_id, e.sink_node_id} <= pasted)
    assert (copy.outlet_port_id, copy.inlet_port_id) == ("right_0", "left_0")
    assert copy.edge_id != original.edge_id
    assert copy.is_valid()
    assert original.is_valid()
    assert len(graph.edge_wrappers) == 2
    # Re-linking the pasted edge grows no second slot.
    assert sorted(graph.node_wrappers[copy.source_node_id].node.ports) == sorted(a.node.ports)
    assert sorted(graph.node_wrappers[copy.sink_node_id].node.ports) == sorted(b.node.ports)


def test_a_reroute_splits_a_note_link(graph):
    from haywire.barn.builtin.nodes.reroute import RerouteNode
    from haywire.core.types import WireRole
    from haywire.core.undo.actions.graph_actions import SplitEdgeWithRerouteAction

    a, b = _notes(graph, 2)
    edge = make_edge(graph, a.node_id, "right_0", b.node_id, "left_0")
    graph.force_validation()

    split = SplitEdgeWithRerouteAction(
        graph, edge.edge_id, (200, 0), RerouteNode.class_identity.registry_key
    )
    split.execute()
    graph.force_validation()

    assert {(e.source_node_id, e.sink_node_id) for e in graph.edge_wrappers.values()} == {
        (a.node_id, split.reroute_node_id),
        (split.reroute_node_id, b.node_id),
    }
    for half in graph.edge_wrappers.values():
        assert half.is_valid()
        assert half.wire_type is not None
        assert half.wire_type.role is WireRole.VISUAL
