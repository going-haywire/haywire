"""Tests for control-edge payloads.

A CONTROL (EXEC) edge carries an optional ``dict`` payload. Because control
edges build an adapter chain, the source EXEC outlet gets an eager ``Pipe``,
so writing the outlet propagates the payload to the linked EXEC inlet — the same
machinery DATA outlets use.

Nodes that need to pass a payload through a control edge must do so explicitly
via ``out()``; there is no automatic transparent-conduit fallback.
"""

import pytest

from haywire.core.execution.event_source import SystemEventType
from haywire.core.execution.interpreter import Interpreter
from haywire.core.graph.base import BaseGraph

from tests.conftest import make_edge, make_node


@pytest.mark.integration
class TestControlPayload:
    def _exec_linked_nodes(self, graph: BaseGraph):
        """Two EdgeLinkTestNodes wired source.execute_out → sink.execute_inlet."""
        from haybale_testing.nodes.testbed.edge_link_test import EdgeLinkTestNode

        source = make_node(graph, EdgeLinkTestNode.class_identity.registry_key, position=(100, 100))
        sink = make_node(graph, EdgeLinkTestNode.class_identity.registry_key, position=(300, 100))
        edge = make_edge(graph, source.node_id, "execute_out", sink.node_id, "execute_inlet")
        return source, sink, edge

    def test_exec_edge_builds_adapter_chain(self, graph_with_library_system: BaseGraph, library_system):
        """A CONTROL edge now builds a chain (Core #1) so it can carry a payload."""
        graph = graph_with_library_system
        _, _, edge = self._exec_linked_nodes(graph)

        assert edge is not None
        assert edge.is_control_edge()
        assert edge.state.is_valid()
        # An EXEC→EXEC edge resolves to a trivial (same-type) chain, not None.
        assert edge.first_adapter is not None

    def test_writing_exec_outlet_propagates_payload(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """Writing the EXEC outlet eagerly pushes the payload to the EXEC inlet.

        This is the ``out('execute_out', payload)`` path: the outlet's eager
        Pipe propagates without any VM involvement.
        """
        graph = graph_with_library_system
        source, sink, _ = self._exec_linked_nodes(graph)

        outlet = source.node.ports["execute_out"]
        inlet = sink.node.ports["execute_inlet"]

        payload = {"hits": 3}
        outlet.set_value(payload)

        assert inlet.get_value() == payload


@pytest.mark.integration
@pytest.mark.slow
class TestControlPayloadEndToEnd:
    """Run a real assembled flow and watch a payload travel down EXEC edges.

    Chain: TestBeginPlay → conduit_a → conduit_b → sink, all wired exec→exec.
    Nodes must explicitly write their outlet via ``out()`` to propagate a payload;
    there is no automatic transparent-conduit fallback.
    """

    def _build_chain(self, graph: BaseGraph):
        from haybale_testing.nodes.testbed.begin_play_node import TestBeginPlayNode
        from haybale_testing.nodes.testbed.control_payload_node import ControlPayloadTestNode

        begin = make_node(graph, TestBeginPlayNode.class_identity.registry_key, position=(0, 0))
        conduit_a = make_node(graph, ControlPayloadTestNode.class_identity.registry_key, position=(200, 0))
        conduit_b = make_node(graph, ControlPayloadTestNode.class_identity.registry_key, position=(400, 0))
        sink = make_node(graph, ControlPayloadTestNode.class_identity.registry_key, position=(600, 0))

        make_edge(graph, begin.node_id, "exec", conduit_a.node_id, "exec_in")
        make_edge(graph, conduit_a.node_id, "exec_out", conduit_b.node_id, "exec_in")
        make_edge(graph, conduit_b.node_id, "exec_out", sink.node_id, "exec_in")

        return conduit_a, conduit_b, sink

    def test_payload_chains_through_multiple_silent_nodes(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """With NO node writing its outlet, nothing spurious propagates.

        The event node fires ``exec`` without a payload, so each conduit enters
        with the EXEC empty-payload default (``{}``) and forwards it — the
        fallback must not synthesise a value out of thin air.
        """
        graph = graph_with_library_system
        _, conduit_b, sink = self._build_chain(graph)
        # No emit_payload set anywhere → all conduits are pure pass-through.

        interpreter = Interpreter()
        interpreter.load_graph(graph)
        try:
            interpreter.dispatch_system_event(SystemEventType.BEGIN_PLAY)
            interpreter.wait_all(timeout=5.0)
        finally:
            interpreter.shutdown()

        # EXEC's empty-payload default is {} (see EXEC.create_default), not None.
        assert conduit_b.node.received == {}
        assert sink.node.received == {}
