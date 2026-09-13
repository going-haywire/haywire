"""Tests for ArrayType._configure_port's flow-type fixup.

``ArrayType`` declares no ``flow_type`` of its own (its ``class_identity``
defaults to ``FlowType.NONE``), so ``DataPort.__post_init__`` computes
``allow_multiple_links`` against ``NONE`` at construction time. ``_configure_port``
then corrects ``flow_type`` to the element type's (e.g. ``DATA``) — and must also
re-derive ``allow_multiple_links``, or an array outlet ends up DATA-typed but
stuck refusing a second edge.
"""

import pytest

from haywire.core.graph.base import BaseGraph
from haywire.core.types.enums import FlowType

pytestmark = pytest.mark.integration


def _edge_link_test_node(graph: BaseGraph):
    from haybale_testing.nodes.testbed.edge_link_test import EdgeLinkTestNode

    key = EdgeLinkTestNode.class_identity.registry_key
    wrapper = graph.create_node_wrapper(key, position=(100, 100))
    return wrapper.node


class TestArrayTypeOutletConnectionRule:
    """An ArrayType outlet over a DATA element type allows multiple links,
    exactly like a scalar DATA outlet — see DataPort.__post_init__."""

    def test_array_outlet_over_data_element_allows_multiple_links(self, graph_with_library_system):
        node = _edge_link_test_node(graph_with_library_system)
        outlet = node.ports["array_float_outlet"]

        assert outlet.flow_type == FlowType.DATA
        assert outlet.allow_multiple_links is True

    def test_array_inlet_over_data_element_keeps_single_link_default(self, graph_with_library_system):
        """Only the outlet rule changes; a DATA inlet stays single-link (the
        DataPort.__post_init__ default), same as a scalar DATA inlet."""
        node = _edge_link_test_node(graph_with_library_system)
        inlet = node.ports["pooled_array_string_inlet"]

        # Wrapped in PooledType, whose own _configure_port sets this True —
        # confirm the ArrayType layer beneath it still resolves to DATA.
        assert inlet.flow_type == FlowType.DATA

    def test_array_outlet_color_follows_element_type(self, graph_with_library_system):
        """_configure_port's flow_type fixup and its color fixup are the same
        codepath; a passing color assertion pins down that we didn't break it
        while touching allow_multiple_links alongside it."""
        from haywire.barn.builtin.types import FLOAT

        node = _edge_link_test_node(graph_with_library_system)
        outlet = node.ports["array_float_outlet"]

        assert outlet.color == FLOAT.class_identity.color

    def test_two_edges_link_from_the_same_array_outlet(self, graph_with_library_system):
        """End-to-end regression: a second edge from an ArrayType outlet must
        link, not displace the first (the bug this module exists to catch)."""
        graph = graph_with_library_system
        node_a = _edge_link_test_node(graph)
        node_b = _edge_link_test_node(graph)
        node_c = _edge_link_test_node(graph)

        edge1 = graph.create_edge_wrapper(
            node_a.wrapper.node_id, "array_float_outlet", node_b.wrapper.node_id, "pooled_array_string_inlet"
        )
        edge2 = graph.create_edge_wrapper(
            node_a.wrapper.node_id, "array_float_outlet", node_c.wrapper.node_id, "pooled_array_string_inlet"
        )

        assert edge1.state.is_valid()
        assert edge2.state.is_valid()
