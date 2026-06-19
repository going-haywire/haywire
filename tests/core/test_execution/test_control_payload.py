"""Tests for control-edge payloads.

A CONTROL (EXEC) edge may carry an optional ``dict`` payload. Because control
edges now build an adapter chain, the source EXEC outlet gets an eager ``Pipe``,
so writing the outlet propagates the payload to the linked EXEC inlet — the same
machinery DATA outlets use. The VM additionally forwards the entered payload when
a worker fires an outlet without writing it (transparent-conduit fallback).

These tests cover the feature at two altitudes:

1. The port/edge layer plus the VM helper (``_fallback_control_payload``)
   directly, using the testbed ``EdgeLinkTestNode`` which exposes EXEC pins.
2. End-to-end through a real assembled flow run by the ``Interpreter``, proving
   a payload reaches a downstream control inlet *even when an intermediate
   node's worker never writes its outlet* — the headline feature.
"""

import haywire.core.graph.editor  # noqa: F401  (import first, per CLAUDE.md)

import pytest

from haywire.core.execution.event_source import SystemEventType
from haywire.core.execution.interpreter import Interpreter
from haywire.core.execution.vm import HaywireVM
from haywire.core.graph.base import BaseGraph


@pytest.mark.integration
class TestControlPayload:
    def _exec_linked_nodes(self, graph: BaseGraph):
        """Two EdgeLinkTestNodes wired source.execute_out → sink.execute_inlet."""
        from haybale_testing.nodes.testbed.edge_link_test import EdgeLinkTestNode

        source = graph.create_node_wrapper(EdgeLinkTestNode.class_identity.registry_key, position=(100, 100))
        sink = graph.create_node_wrapper(EdgeLinkTestNode.class_identity.registry_key, position=(300, 100))
        edge = graph.create_edge_wrapper(source.node_id, "execute_out", sink.node_id, "execute_inlet")
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

    def test_silent_node_forwards_entered_payload(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """A worker that fires an outlet without writing it forwards the inlet payload.

        Drives ``_push_control_payload`` directly: the source has a value on the
        inlet it was 'entered' through, did NOT write the outlet, so the helper
        writes the inlet value onto the outlet, which eagerly propagates.
        """
        graph = graph_with_library_system
        source, sink, _ = self._exec_linked_nodes(graph)

        # Simulate the pulse arriving on the source with a payload.
        source.node.ports["execute_inlet"].set_value({"k": "v"})
        outlet = source.node.ports["execute_out"]
        sink_inlet = sink.node.ports["execute_inlet"]
        assert not outlet._is_set_by_node  # worker has not written it

        vm = HaywireVM()
        vm._fallback_control_payload(source.node, "execute_inlet", "execute_out")

        # Forwarded payload reached the sink, and the sticky flag is cleared.
        assert sink_inlet.get_value() == {"k": "v"}
        assert not outlet._is_set_by_node

    def test_written_outlet_is_not_overwritten_by_fallback(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """When the worker wrote the outlet, the fallback must not clobber it.

        ``_push_control_payload`` should leave the eagerly-pushed value in place
        and only clear the sticky ``_is_set_by_node`` flag.
        """
        graph = graph_with_library_system
        source, sink, _ = self._exec_linked_nodes(graph)

        outlet = source.node.ports["execute_out"]
        sink_inlet = sink.node.ports["execute_inlet"]

        # Worker writes the outlet (sets _is_set_by_node, eager-propagates).
        outlet.set_value({"written": True})
        assert outlet._is_set_by_node
        # A different value sits on the entered inlet — must be ignored.
        source.node.ports["execute_inlet"].set_value({"entered": True})

        vm = HaywireVM()
        vm._fallback_control_payload(source.node, "execute_inlet", "execute_out")

        assert sink_inlet.get_value() == {"written": True}
        assert not outlet._is_set_by_node  # flag reset for next frame


@pytest.mark.integration
@pytest.mark.slow
class TestControlPayloadEndToEnd:
    """Run a real assembled flow and watch a payload travel down EXEC edges.

    Chain: TestBeginPlay → conduit_a → conduit_b → sink, all wired exec→exec.
    ``conduit_a`` writes an explicit payload via ``out()``; ``conduit_b`` writes
    nothing and just returns its outlet, so the VM's transparent-conduit
    fallback must forward the payload through it untouched.
    """

    def _build_chain(self, graph: BaseGraph):
        from haybale_testing.nodes.testbed.begin_play_node import TestBeginPlayNode
        from haybale_testing.nodes.testbed.control_payload_node import ControlPayloadTestNode

        begin = graph.create_node_wrapper(TestBeginPlayNode.class_identity.registry_key, position=(0, 0))
        conduit_a = graph.create_node_wrapper(
            ControlPayloadTestNode.class_identity.registry_key, position=(200, 0)
        )
        conduit_b = graph.create_node_wrapper(
            ControlPayloadTestNode.class_identity.registry_key, position=(400, 0)
        )
        sink = graph.create_node_wrapper(
            ControlPayloadTestNode.class_identity.registry_key, position=(600, 0)
        )

        graph.create_edge_wrapper(begin.node_id, "exec", conduit_a.node_id, "exec_in")
        graph.create_edge_wrapper(conduit_a.node_id, "exec_out", conduit_b.node_id, "exec_in")
        graph.create_edge_wrapper(conduit_b.node_id, "exec_out", sink.node_id, "exec_in")

        return conduit_a, conduit_b, sink

    def test_payload_forwarded_through_silent_node(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """conduit_a emits a payload; conduit_b forwards it without writing it."""
        graph = graph_with_library_system
        conduit_a, conduit_b, sink = self._build_chain(graph)

        payload = {"hits": 7, "source": "conduit_a"}
        # conduit_a explicitly writes the payload; conduit_b leaves emit_payload
        # at the default None so its worker never touches its outlet.
        conduit_a.node.emit_payload = payload

        interpreter = Interpreter()
        interpreter.load_graph(graph)
        try:
            triggered = interpreter.dispatch_system_event(SystemEventType.BEGIN_PLAY)
            assert triggered == 1
            interpreter.wait_all(timeout=5.0)
        finally:
            interpreter.shutdown()

        # conduit_b received the explicit payload on its entered inlet,
        assert conduit_b.node.received == payload
        # and even though its worker wrote nothing, the payload reached the sink.
        assert sink.node.received == payload

        # Assert the individual key-value pairs survived the trip end-to-end,
        # untouched by the silent conduit in the middle.
        received = sink.node.received
        assert received is not None
        assert received["hits"] == 7
        assert received["source"] == "conduit_a"

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
