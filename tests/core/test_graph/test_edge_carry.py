"""Paste, Subgraph instantiation, collapse and expand keep an edge's propagation and style (Q27, Q73)."""

from typing import Any

import pytest

from haywire.core.graph.base import BaseGraph
from haywire.core.graph.scheduler import SyncScheduler
from haywire.core.types import Propagation

from tests.conftest import make_edge, make_node

pytestmark = pytest.mark.integration

_ADD = "haybale-testing:node:TestAddFloatNode"
_CARD = "haywire-core:node:GraphNode"
_INPUT = "haywire-core:node:SubgraphInputNode"
_OUTPUT = "haywire-core:node:SubgraphOutputNode"


@pytest.fixture
def graph(library_system) -> BaseGraph:
    return BaseGraph(filestem="Carry Graph", validation_scheduler=SyncScheduler())


def _probe_key() -> str:
    from haybale_testing.nodes.testbed.visual_probe import VisualProbeNode

    return VisualProbeNode.class_identity.registry_key


def _pair(graph):
    """A lazy data edge between two adders, and a styled visual edge between two probes."""
    a = make_node(graph, _ADD, position=(0, 0))
    b = make_node(graph, _ADD, position=(300, 0))
    lazy = make_edge(graph, a.node_id, "result", b.node_id, "value_a", propagation=Propagation.LAZY)
    p = make_node(graph, _probe_key(), position=(0, 200))
    q = make_node(graph, _probe_key(), position=(300, 200))
    styled = make_edge(graph, p.node_id, "note_out", q.node_id, "note_in", style={"color": "#ff0000"})
    graph.force_validation()
    return [a, b, p, q], lazy, styled


def _edges_by_port(graph):
    return {(e.outlet_port_id, e.inlet_port_id): e for e in graph.edge_wrappers.values()}


def _color(edge) -> Any:
    assert edge.style is not None
    return edge.style._to_dict()["values"].get("color")


def test_remap_carries_style():
    from haywire.core.graph.utils.node_remap import remap_node_ids

    minted = iter(["new_a", "new_b"])
    remap = remap_node_ids(
        nodes={"n1": {"registry_key": "k"}, "n2": {"registry_key": "k"}},
        edges={
            "e": {
                "source_node_id": "n1",
                "outlet_port_id": "o",
                "sink_node_id": "n2",
                "inlet_port_id": "i",
                "propagation": "lazy",
                "style": {"color": "#ff0000"},
            }
        },
        mint_id=lambda key: next(minted),
    )
    (edge,) = remap.edges
    assert edge.propagation == "lazy"
    assert edge.style == {"color": "#ff0000"}


def test_paste_keeps_propagation_and_style(graph):
    from haywire.core.graph.clipboard import build_clipboard_payload
    from haywire.core.undo.actions.graph_actions import PasteClipboardAction

    nodes, lazy, styled = _pair(graph)
    payload = build_clipboard_payload(
        graph, [n.node_id for n in nodes], [lazy.edge_id, styled.edge_id], session_id="test"
    )
    paste = PasteClipboardAction(graph=graph, payload=payload, paste_x=0.0, paste_y=600.0)
    paste.execute()
    graph.force_validation()

    pasted = [graph.get_edge_wrapper(edge_id) for edge_id in paste.new_edge_ids]
    lazy_copy = next(e for e in pasted if e is not None and e.outlet_port_id == "result")
    styled_copy = next(e for e in pasted if e is not None and e.outlet_port_id == "note_out")
    assert lazy_copy.propagation is Propagation.LAZY
    assert _color(styled_copy) == "#ff0000"


def test_instantiate_keeps_propagation_and_style(graph):
    from haywire.core.graph.subgraph import SubgraphDefinition

    nodes, lazy, styled = _pair(graph)
    definition = graph.add_subgraph(SubgraphDefinition(key="carry", validation_scheduler=SyncScheduler()))
    definition.instantiate(
        {n.node_id: n.serialize(include_data=True) for n in nodes},
        {lazy.edge_id: lazy.serialize(), styled.edge_id: styled.serialize()},
    )
    definition.force_validation()
    edges = _edges_by_port(definition)
    assert edges[("result", "value_a")].propagation is Propagation.LAZY
    assert _color(edges[("note_out", "note_in")]) == "#ff0000"


def test_collapse_and_expand_keep_propagation_and_style(graph):
    from haywire.core.undo.actions.graph_actions import CollapseToGraphNodeAction, ExpandGraphNodeAction

    nodes, _, _ = _pair(graph)
    collapse = CollapseToGraphNodeAction(
        graph=graph,
        node_ids=[n.node_id for n in nodes],
        card_registry_key=_CARD,
        input_registry_key=_INPUT,
        output_registry_key=_OUTPUT,
        label="Group",
    )
    collapse.execute()
    graph.force_validation()
    definition = graph.get_subgraph(collapse.subgraph_key)
    assert definition is not None
    definition.force_validation()
    inside = _edges_by_port(definition)
    assert inside[("result", "value_a")].propagation is Propagation.LAZY
    assert _color(inside[("note_out", "note_in")]) == "#ff0000"

    ExpandGraphNodeAction(graph=graph, node_id=collapse.card_node_id).execute()
    graph.force_validation()
    back = _edges_by_port(graph)
    assert back[("result", "value_a")].propagation is Propagation.LAZY
    assert _color(back[("note_out", "note_in")]) == "#ff0000"


def _reroute_key() -> str:
    from haywire.barn.builtin.nodes.reroute import RerouteNode

    return RerouteNode.class_identity.registry_key


def test_split_keeps_propagation_and_style_on_both_halves(graph):
    """F22: both edges a split leaves take the original's values."""
    from haywire.core.undo.actions.graph_actions import SplitEdgeWithRerouteAction

    _, lazy, styled = _pair(graph)
    for edge, check in ((lazy, "lazy"), (styled, "style")):
        split = SplitEdgeWithRerouteAction(graph, edge.edge_id, (150, 0), _reroute_key())
        split.execute()
        graph.force_validation()
        halves = [
            e
            for e in graph.edge_wrappers.values()
            if split.reroute_node_id in (e.source_node_id, e.sink_node_id)
        ]
        assert len(halves) == 2
        for half in halves:
            if check == "lazy":
                assert half.propagation is Propagation.LAZY
            else:
                assert _color(half) == "#ff0000"


def test_dissolve_keeps_the_downstream_edges_values(graph):
    """F22: dissolving a reroute bridges each downstream edge with its own propagation."""
    from haywire.core.undo.actions.graph_actions import DissolveRerouteAction, SplitEdgeWithRerouteAction

    nodes, lazy, _ = _pair(graph)
    split = SplitEdgeWithRerouteAction(graph, lazy.edge_id, (150, 0), _reroute_key())
    split.execute()
    graph.force_validation()
    assert split.reroute_node_id is not None
    upstream = next(e for e in graph.edge_wrappers.values() if e.sink_node_id == split.reroute_node_id)
    upstream.propagation = Propagation.EAGER

    DissolveRerouteAction(graph, split.reroute_node_id).execute()
    graph.force_validation()
    assert _edges_by_port(graph)[("result", "value_a")].propagation is Propagation.LAZY


def test_expand_keeps_the_card_edges_values(graph):
    """F22: an edge into a Group's card keeps its propagation when expand bridges it inside."""
    from haywire.core.undo.actions.graph_actions import CollapseToGraphNodeAction, ExpandGraphNodeAction

    nodes, _, _ = _pair(graph)
    a, b = nodes[0], nodes[1]
    collapse = CollapseToGraphNodeAction(
        graph=graph,
        node_ids=[b.node_id],
        card_registry_key=_CARD,
        input_registry_key=_INPUT,
        output_registry_key=_OUTPUT,
        label="Group",
    )
    collapse.execute()
    graph.force_validation()
    card_edge = next(e for e in graph.edge_wrappers.values() if e.sink_node_id == collapse.card_node_id)
    card_edge.propagation = Propagation.LAZY

    ExpandGraphNodeAction(graph=graph, node_id=collapse.card_node_id).execute()
    graph.force_validation()
    bridged = next(e for e in graph.edge_wrappers.values() if e.source_node_id == a.node_id)
    assert bridged.propagation is Propagation.LAZY
