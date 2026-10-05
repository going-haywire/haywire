"""An ArrayType port takes its element's wire type and colour, and an array outlet on a data wire
allows several links like any data outlet."""

import pytest

from haywire.core.graph.base import BaseGraph
from haywire.barn.builtin.wires import DataWire

pytestmark = pytest.mark.integration


def _edge_link_test_node(graph: BaseGraph):
    from haybale_testing.nodes.testbed.edge_link_test import EdgeLinkTestNode

    key = EdgeLinkTestNode.class_identity.registry_key
    wrapper = graph.create_node_wrapper(key, position=(100, 100))
    assert wrapper is not None
    return wrapper.node


class TestArrayTypeOutletConnectionRule:
    """An ArrayType outlet over a DATA element type allows multiple links,
    exactly like a scalar DATA outlet — see DataPort.__post_init__."""

    def test_array_outlet_over_data_element_allows_multiple_links(self, graph_with_library_system):
        node = _edge_link_test_node(graph_with_library_system)
        outlet = node.ports["array_float_outlet"]

        assert outlet.wire_type.id == DataWire.id
        assert outlet.allow_multiple_links is True

    def test_pooled_array_inlet_over_data_element_is_multi_link(self, graph_with_library_system):
        """A pooled array inlet resolves to the data wire and allows several links
        (PooledType sets multi-link)."""
        node = _edge_link_test_node(graph_with_library_system)
        inlet = node.ports["pooled_array_string_inlet"]

        # Wrapped in PooledType, whose own _configure_port sets multi-link; the ArrayType
        # layer beneath it still resolves to the data wire.
        assert inlet.wire_type.id == DataWire.id
        assert inlet.allow_multiple_links is True

    def test_array_outlet_color_follows_element_type(self, graph_with_library_system):
        """_configure_port takes the colour from the element that declares the wire type."""
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
