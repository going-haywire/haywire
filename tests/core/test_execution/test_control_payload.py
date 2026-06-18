"""Tests for control-edge payloads.

A CONTROL (EXEC) edge may carry an optional ``dict`` payload. Because control
edges now build an adapter chain, the source EXEC outlet gets an eager ``Pipe``,
so writing the outlet propagates the payload to the linked EXEC inlet — the same
machinery DATA outlets use. The VM additionally forwards the entered payload when
a worker fires an outlet without writing it (transparent-conduit fallback).

These tests exercise the mechanism at the port/edge layer plus the VM helper
directly, using the testbed ``EdgeLinkTestNode`` which exposes EXEC pins.
"""

import haywire.core.graph.editor  # noqa: F401  (import first, per CLAUDE.md)

import pytest

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
