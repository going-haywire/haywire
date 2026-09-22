"""An edit made inside a Subgraph reaches the host graph.

The host's own validation never runs for an edit made inside one of its
Subgraphs — the two graphs own separate validation managers, and only the
Graph-node spans both. Without the card reporting it, a host stays clean while
its interior is edited, and a running graph is never reassembled.

A move is the case that pins the contract: it persists (``props.posX/posY``)
but reassembles nothing, so a cascade gated on ``requires_graph_reassembly``
drops it silently.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, cast

import pytest

from haywire.core.graph.base import BaseGraph
from haywire.core.graph.scheduler import ThreadingTimerScheduler
from haywire.core.graph.subgraph import SubgraphDefinition

from tests.conftest import make_node

if TYPE_CHECKING:
    from haywire.barn.builtin.nodes.graph_node import GraphNode

pytestmark = [pytest.mark.integration]

_ADD_FLOAT = "haybale-testing:node:TestAddFloatNode"
_OUTPUT = "haywire-core:node:SubgraphOutputNode"
_CARD = "haywire-core:node:GraphNode"

#: Long enough for both debounce windows (50ms each, host after Subgraph) to
#: close on a loaded machine. Real time, because a real background timer is
#: what the cascade rides on.
_SETTLE_S = 0.3


def _slot(node) -> str:
    from haywire.barn.builtin.types import ADD

    return next(p.id for p in node.get_all_ports() if p.type_cls is not None and issubclass(p.type_cls, ADD))


@pytest.fixture
def card_over_a_subgraph(graph_with_library_system: BaseGraph):
    """A host graph carrying a Graph-node, both debounced as the studio runs them."""
    from haywire.barn.builtin.nodes.graph_node import SUBGRAPH_KEY

    graph = graph_with_library_system
    # The fixture's graph is synchronous; the studio's is debounced, and marks
    # only coalesce when they are.
    graph._validation._scheduler = ThreadingTimerScheduler()
    graph._validation._debounce_ms = 50.0

    definition = graph.add_subgraph(SubgraphDefinition(key="sg", label="Group", validation_delay_ms=50.0))
    output_node = make_node(definition, _OUTPUT)
    interior = make_node(definition, _ADD_FLOAT)

    card = make_node(graph, _CARD, node_data={"store": {SUBGRAPH_KEY: "sg"}})
    cast("GraphNode", card.node).reconcile_interface()

    # Drain the setup's own marks rather than sleeping them off: each test
    # subscribes afterwards and must see only what it does itself.
    graph.force_validation()

    return graph, definition, card, output_node, interior


def _record(graph: BaseGraph) -> list:
    """Collect the host's validation batches from here on."""
    seen: list = []
    graph.subscribe_to_validation(seen.append)
    return seen


def test_a_quiet_subgraph_leaves_the_host_alone(card_over_a_subgraph):
    """No edit, no report — the cascade must not fire on its own."""
    graph, _definition, _card, _output_node, _interior = card_over_a_subgraph
    seen = _record(graph)

    time.sleep(_SETTLE_S)

    assert seen == []


def test_moving_a_node_inside_reports_to_the_host(card_over_a_subgraph):
    """A move persists but reassembles nothing, so only ``requires_save`` catches it."""
    graph, definition, _card, _output_node, interior = card_over_a_subgraph
    seen = _record(graph)

    definition.move_node(interior.node_id, 123.0, 456.0)
    time.sleep(_SETTLE_S)

    assert any(result.requires_save() for result in seen)


def test_growing_an_interface_reaches_the_card(card_over_a_subgraph):
    """The card mirrors a port grown inside, without anyone calling reconcile."""
    from haywire.barn.builtin.types import FLOAT

    graph, definition, card, output_node, _interior = card_over_a_subgraph
    seen = _record(graph)

    producer = make_node(definition, _ADD_FLOAT)
    with producer.node.rejig():
        producer.node.add(FLOAT.as_outlet("score", label="Match Score", default=0.6))
    slot_id = _slot(output_node.node)
    definition.create_edge_wrapper(producer.node_id, "score", output_node.node_id, slot_id)
    time.sleep(_SETTLE_S)

    assert f"out_{slot_id}" in card.node.ports
    assert any(result.requires_save() for result in seen)


class TestLoadingIsNotAnEdit:
    """Opening a file must not report it as changed.

    The cards are subscribed from ``post_init``, so they are listening while
    the Subgraphs around them are still being populated, and every one of those
    load-time batches looks exactly like a user's edit. The open path flushes
    before it subscribes, which only holds if the flush reaches the Subgraphs
    too and they debounce the way their host does.
    """

    @pytest.fixture
    def loaded(self, graph_with_library_system: BaseGraph, tmp_path):
        """A saved graph carrying a Subgraph, loaded back as the studio opens one."""
        from haywire.barn.builtin.types import FLOAT
        from haywire.barn.builtin.nodes.graph_node import SUBGRAPH_KEY

        source = graph_with_library_system
        definition = source.add_subgraph(
            SubgraphDefinition(key="sg", label="Group", validation_delay_ms=50.0)
        )
        output_node = make_node(definition, _OUTPUT)
        producer = make_node(definition, _ADD_FLOAT)
        with producer.node.rejig():
            producer.node.add(FLOAT.as_outlet("score", label="Match Score", default=0.6))
        definition.create_edge_wrapper(
            producer.node_id, "score", output_node.node_id, _slot(output_node.node)
        )
        card = make_node(source, _CARD, node_data={"store": {SUBGRAPH_KEY: "sg"}})
        cast("GraphNode", card.node).reconcile_interface()
        source.force_validation()

        path = tmp_path / "with_subgraph.haywire"
        source.save_to_file(str(path))
        return str(path)

    def test_the_subgraph_queue_is_empty_after_the_flush(self, loaded, graph_with_library_system):
        """``force_validation`` reaches the Subgraphs, or marks land after it."""
        graph = graph_with_library_system
        graph._validation._scheduler = ThreadingTimerScheduler()

        graph.load_from_file(loaded)
        graph.force_validation()

        for definition in graph.subgraphs.values():
            pending = definition._validation
            assert not pending._dirty_nodes
            assert not pending._dirty_edges

    def test_loading_leaves_the_host_clean(self, loaded, graph_with_library_system):
        """Nothing a save would record, so the app must not mark the file unsaved."""
        graph = graph_with_library_system
        graph._validation._scheduler = ThreadingTimerScheduler()

        graph.load_from_file(loaded)
        graph.force_validation()

        # Subscribed after the flush, exactly as the open path does.
        seen = _record(graph)
        time.sleep(_SETTLE_S)

        assert [r for r in seen if r.requires_save()] == []
