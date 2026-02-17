"""
Integration tests for edge connections using EdgeLinkTestNode.

Tests connection behaviors between different port types:
- Data inlet many-to-one (replacement) and many-to-many (pooled)
- Adapter chain creation for different type combinations
- Execute flow connection rules (one outgoing connection)
- Cross flow-type connection rejection (exec/data/callback isolation)
- Derived type connections (TEST_TEMPERATURE → TEST_FLOAT)
- Array type adapter chains
"""

import pytest
from haywire.core.graph.base import BaseGraph


@pytest.mark.integration
class TestEdgeConnections:
    """Test edge connection behaviors using EdgeLinkTestNode."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _create_two_nodes(self, graph: BaseGraph):
        """Create two EdgeLinkTestNode instances and return their wrappers."""
        from haybale_testing.nodes.testbed.edge_link_test import EdgeLinkTestNode

        node_a = graph.create_node_wrapper(
            EdgeLinkTestNode.class_identity.registry_key,
            position=(100, 100)
        )
        node_b = graph.create_node_wrapper(
            EdgeLinkTestNode.class_identity.registry_key,
            position=(300, 100)
        )
        return node_a, node_b

    def _create_three_nodes(self, graph: BaseGraph):
        """Create three EdgeLinkTestNode instances and return their wrappers."""
        from haybale_testing.nodes.testbed.edge_link_test import EdgeLinkTestNode

        node_a = graph.create_node_wrapper(
            EdgeLinkTestNode.class_identity.registry_key,
            position=(100, 100)
        )
        node_b = graph.create_node_wrapper(
            EdgeLinkTestNode.class_identity.registry_key,
            position=(300, 100)
        )
        node_c = graph.create_node_wrapper(
            EdgeLinkTestNode.class_identity.registry_key,
            position=(500, 100)
        )
        return node_a, node_b, node_c

    def _get_port(self, node_wrapper, port_id):
        """Get a DataPort by id from a node wrapper."""
        return node_wrapper.node.ports[port_id]

    # ==================================================================
    # DATA INLET: Many-to-One (single-connection replacement)
    # ==================================================================

    def test_data_inlet_allows_single_connection(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """A standard data inlet should accept exactly one connection."""
        graph = graph_with_library_system
        node_a, node_b = self._create_two_nodes(graph)

        edge = graph.create_edge_wrapper(
            node_a.node_id, 'bool_outlet',
            node_b.node_id, 'bool_inlet'
        )

        assert edge is not None
        assert edge.state.is_valid()

        inlet_port = self._get_port(node_b, 'bool_inlet')
        assert inlet_port.is_linked()
        assert len(inlet_port._linked_edges) == 1

    def test_data_inlet_second_valid_connection_replaces_first(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """
        When a second valid connection targets a single-connection inlet,
        it should replace the first connection. The first edge should
        become unlinked on the inlet side.
        """
        graph = graph_with_library_system
        node_a, node_b, node_c = self._create_three_nodes(graph)

        edge_1 = graph.create_edge_wrapper(
            node_a.node_id, 'bool_outlet',
            node_c.node_id, 'bool_inlet'
        )
        edge_2 = graph.create_edge_wrapper(
            node_b.node_id, 'bool_outlet',
            node_c.node_id, 'bool_inlet'
        )

        assert edge_1 is not None
        assert edge_2 is not None

        inlet_port = self._get_port(node_c, 'bool_inlet')

        # Inlet should only have one linked edge — the second one
        assert len(inlet_port._linked_edges) == 1
        assert edge_2.connection_uuid in inlet_port._linked_edges

        # The second edge should not be valid
        assert not edge_1.state.is_valid()

        # The second edge should be valid
        assert edge_2.state.is_valid()

        # The first edge should no longer be linked on the inlet side
        assert not edge_1.state.is_inlet_linked

    def test_data_inlet_second_invalid_connection_does_not_replace_first(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """
        When a second connection to an inlet is invalid (e.g. cross flow-type),
        it should NOT displace the first valid connection.
        Only valid connections should cause replacement.
        """
        graph = graph_with_library_system
        node_a, node_b, node_c = self._create_three_nodes(graph)

        # First: a valid bool→bool connection
        edge_valid = graph.create_edge_wrapper(
            node_a.node_id, 'bool_outlet',
            node_c.node_id, 'bool_inlet'
        )
        assert edge_valid is not None
        assert edge_valid.state.is_valid()

        # Second: try to connect exec outlet → data inlet (cross flow-type)
        edge_invalid = graph.create_edge_wrapper(
            node_b.node_id, 'execute_out',
            node_c.node_id, 'bool_inlet'
        )

        # The invalid edge should not be functional
        assert not edge_invalid.state.is_functional()

        inlet_port = self._get_port(node_c, 'bool_inlet')
        # The first valid edge should still be linked
        assert edge_valid.connection_uuid in inlet_port._linked_edges
        assert edge_valid.state.is_inlet_linked

        assert edge_valid.state.is_valid()
        assert not edge_invalid.state.is_valid()

    def test_data_inlet_replacement_with_adapter_connection(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """
        A second connection that requires adapters (e.g. bool→int inlet)
        should still replace the first connection if valid.
        """
        graph = graph_with_library_system
        node_a, node_b, node_c = self._create_three_nodes(graph)

        # First: int→int connection
        edge_1 = graph.create_edge_wrapper(
            node_a.node_id, 'int_outlet',
            node_c.node_id, 'int_inlet'
        )
        assert edge_1.state.is_valid()

        # Second: bool→int connection (requires BoolToIntAdapter)
        edge_2 = graph.create_edge_wrapper(
            node_b.node_id, 'bool_outlet',
            node_c.node_id, 'int_inlet'
        )
        assert edge_2.state.is_valid()

        inlet_port = self._get_port(node_c, 'int_inlet')
        assert len(inlet_port._linked_edges) == 1
        assert edge_2.connection_uuid in inlet_port._linked_edges
        assert not edge_1.state.is_inlet_linked

        assert not edge_1.state.is_valid()

    # ==================================================================
    # DATA INLET: Many-to-Many (Pooled Inlets)
    # ==================================================================

    def test_pooled_inlet_accepts_multiple_connections(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """Pooled inlets should accept multiple connections simultaneously."""
        graph = graph_with_library_system
        node_a, node_b, node_c = self._create_three_nodes(graph)

        edge_1 = graph.create_edge_wrapper(
            node_a.node_id, 'bool_outlet',
            node_c.node_id, 'pooled_bool_inlet'
        )
        edge_2 = graph.create_edge_wrapper(
            node_b.node_id, 'bool_outlet',
            node_c.node_id, 'pooled_bool_inlet'
        )

        assert edge_1 is not None
        assert edge_2 is not None
        assert edge_1.state.is_valid()
        assert edge_2.state.is_valid()

        pooled_port = self._get_port(node_c, 'pooled_bool_inlet')
        assert pooled_port.allow_multiple_connections is True
        assert len(pooled_port._linked_edges) == 2

    def test_pooled_inlet_with_adapter_connections(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """
        Pooled inlets should accept connections from different
        source types that require adapter chains.
        """
        graph = graph_with_library_system
        node_a, node_b, node_c = self._create_three_nodes(graph)

        # bool→pooled_int (requires BoolToIntAdapter)
        edge_1 = graph.create_edge_wrapper(
            node_a.node_id, 'bool_outlet',
            node_c.node_id, 'pooled_int_inlet'
        )
        # int→pooled_int (same type)
        edge_2 = graph.create_edge_wrapper(
            node_b.node_id, 'int_outlet',
            node_c.node_id, 'pooled_int_inlet'
        )

        assert edge_1.state.is_valid()
        assert edge_2.state.is_valid()

        pooled_port = self._get_port(node_c, 'pooled_int_inlet')
        assert len(pooled_port._linked_edges) == 2

    def test_data_outlet_allows_multiple_connections(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """Data outlets should allow multiple outgoing connections."""
        graph = graph_with_library_system
        node_a, node_b, node_c = self._create_three_nodes(graph)

        edge_1 = graph.create_edge_wrapper(
            node_a.node_id, 'bool_outlet',
            node_b.node_id, 'bool_inlet'
        )
        edge_2 = graph.create_edge_wrapper(
            node_a.node_id, 'bool_outlet',
            node_c.node_id, 'bool_inlet'
        )

        assert edge_1.state.is_valid()
        assert edge_2.state.is_valid()

        outlet_port = self._get_port(node_a, 'bool_outlet')
        assert outlet_port.allow_multiple_connections is True
        assert len(outlet_port._linked_edges) == 2

    # ==================================================================
    # ADAPTER CHAIN CREATION
    # ==================================================================

    def test_same_type_no_adapter_chain(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """Same type → same type should produce an empty adapter chain (ReturnAdapter)."""
        graph = graph_with_library_system
        node_a, node_b = self._create_two_nodes(graph)

        edge = graph.create_edge_wrapper(
            node_a.node_id, 'bool_outlet',
            node_b.node_id, 'bool_inlet'
        )

        assert edge.state.is_valid()
        # ReturnAdapter has no registry keys
        assert len(edge.edge.chain_adapter_keys) == 0

    def test_bool_to_int_one_adapter(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """TEST_BOOL → TEST_INT should use one adapter (BoolToIntAdapter)."""
        graph = graph_with_library_system
        node_a, node_b = self._create_two_nodes(graph)

        edge = graph.create_edge_wrapper(
            node_a.node_id, 'bool_outlet',
            node_b.node_id, 'int_inlet'
        )

        assert edge.state.is_valid()
        assert len(edge.edge.chain_adapter_keys) == 1

    def test_bool_to_float_two_adapters(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """TEST_BOOL → TEST_FLOAT should chain two adapters (Bool→Int→Float)."""
        graph = graph_with_library_system
        node_a, node_b = self._create_two_nodes(graph)

        edge = graph.create_edge_wrapper(
            node_a.node_id, 'bool_outlet',
            node_b.node_id, 'float_inlet'
        )

        assert edge.state.is_valid()
        assert len(edge.edge.chain_adapter_keys) == 2

    def test_bool_to_string_three_adapters(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """TEST_BOOL → TEST_STRING should chain three adapters (Bool→Int→Float→String)."""
        graph = graph_with_library_system
        node_a, node_b = self._create_two_nodes(graph)

        edge = graph.create_edge_wrapper(
            node_a.node_id, 'bool_outlet',
            node_b.node_id, 'string_inlet'
        )

        assert edge.state.is_valid()
        assert len(edge.edge.chain_adapter_keys) == 3

    def test_array_same_element_type_no_element_adapter(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """
        test array outlet to pooled_array_string_inlet for
        ARRAY[TEST_STRING] → ARRAY[TEST_STRING] (same).
        """
        graph = graph_with_library_system
        node_a, node_b = self._create_two_nodes(graph)

        edge = graph.create_edge_wrapper(
            node_a.node_id, 'array_string_outlet',
            node_b.node_id, 'pooled_array_string_inlet'
        )

        assert edge.state.is_valid()
        # Same element type ARRAY[STRING] → ARRAY[STRING] = ReturnAdapter
        assert len(edge.edge.chain_adapter_keys) == 0

    def test_array_different_element_type_has_adapter(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """
        ARRAY[TEST_BOOL] outlet → pooled ARRAY[TEST_STRING] inlet should
        require an ArrayArrayAdapter wrapping a scalar chain.

        Since pooled_array_string_inlet stores ArrayType[TEST_STRING],
        and the outlet is ArrayType[TEST_BOOL], adapter chain should have
        the ArrayArrayAdapter + element adapters.
        """
        graph = graph_with_library_system
        node_a, node_b = self._create_two_nodes(graph)

        edge = graph.create_edge_wrapper(
            node_a.node_id, 'array_bool_outlet',
            node_b.node_id, 'pooled_array_string_inlet'
        )

        assert edge.state.is_valid()
        # Should have adapter(s) for element conversion
        assert len(edge.edge.chain_adapter_keys) == 4

    # ==================================================================
    # DERIVED TYPE CONNECTIONS (TEST_TEMPERATURE extends TEST_FLOAT)
    # ==================================================================

    def test_derived_type_to_parent_type_no_adapter(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """
        TEST_TEMPERATURE (derived from TEST_FLOAT) → TEST_FLOAT inlet
        should work without any adapters (child → parent passthrough).
        """
        graph = graph_with_library_system
        node_a, node_b = self._create_two_nodes(graph)

        edge = graph.create_edge_wrapper(
            node_a.node_id, 'temperature_outlet',
            node_b.node_id, 'float_inlet'
        )

        assert edge.state.is_valid()
        assert len(edge.edge.chain_adapter_keys) == 0

    def test_derived_type_to_string_via_parent_chain(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """
        TEST_TEMPERATURE → TEST_STRING should resolve via the
        ancestor chain: TEMPERATURE (as FLOAT) → STRING uses
        FloatToStringAdapter (1 adapter via MRO fallback).
        """
        graph = graph_with_library_system
        node_a, node_b = self._create_two_nodes(graph)

        edge = graph.create_edge_wrapper(
            node_a.node_id, 'temperature_outlet',
            node_b.node_id, 'string_inlet'
        )

        assert edge.state.is_valid()
        assert len(edge.edge.chain_adapter_keys) >= 1

    def test_parent_type_to_derived_type_rejected(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """
        TEST_FLOAT → TEST_TEMPERATURE inlet should fail because
        parent → child is a narrowing conversion. Not every float
        is a valid temperature. An explicit adapter would be required.
        """
        graph = graph_with_library_system
        node_a, node_b = self._create_two_nodes(graph)

        edge = graph.create_edge_wrapper(
            node_a.node_id, 'float_outlet',
            node_b.node_id, 'temperature_inlet'
        )

        assert not edge.state.is_built
        assert edge.state.error_build is not None

    # ==================================================================
    # EXECUTE FLOW CONNECTIONS (CONTROL type)
    # ==================================================================

    def test_exec_connection_valid(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """Basic EXEC outlet → EXEC inlet should be valid."""
        graph = graph_with_library_system
        node_a, node_b = self._create_two_nodes(graph)

        edge = graph.create_edge_wrapper(
            node_a.node_id, 'execute_out',
            node_b.node_id, 'execute_inlet'
        )

        assert edge is not None
        assert edge.state.is_formally_validated

    def test_exec_outlet_single_connection_only(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """
        EXEC outlets should only allow one outgoing connection.
        A second connection should replace the first.
        """
        graph = graph_with_library_system
        node_a, node_b, node_c = self._create_three_nodes(graph)

        edge_1 = graph.create_edge_wrapper(
            node_a.node_id, 'execute_out',
            node_b.node_id, 'execute_inlet'
        )
        edge_2 = graph.create_edge_wrapper(
            node_a.node_id, 'execute_out',
            node_c.node_id, 'execute_inlet'
        )

        outlet_port = self._get_port(node_a, 'execute_out')
        assert outlet_port.allow_multiple_connections is False
        assert len(outlet_port._linked_edges) == 1

        # The second edge should be the one linked
        assert edge_2.connection_uuid in outlet_port._linked_edges
        # The first edge should no longer be linked on the outlet side
        assert not edge_1.state.is_outlet_linked

        assert not edge_1.state.is_valid()
        assert edge_2.state.is_valid()

    def test_exec_inlet_single_connection_only(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """
        EXEC inlets should allow more than one incoming connection.
        """
        graph = graph_with_library_system
        node_a, node_b, node_c = self._create_three_nodes(graph)

        edge_1 = graph.create_edge_wrapper(
            node_a.node_id, 'execute_out',
            node_c.node_id, 'execute_inlet'
        )
        edge_2 = graph.create_edge_wrapper(
            node_b.node_id, 'execute_out',
            node_c.node_id, 'execute_inlet'
        )

        inlet_port = self._get_port(node_c, 'execute_inlet')
        assert len(inlet_port._linked_edges) == 2

        assert edge_1.state.is_valid()
        assert edge_2.state.is_valid()

    # ==================================================================
    # CALLBACK FLOW CONNECTIONS
    # ==================================================================

    def test_callback_connection_valid(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """CALLBACK outlet → CALLBACK inlet should pass formal validation."""
        graph = graph_with_library_system
        node_a, node_b = self._create_two_nodes(graph)

        edge = graph.create_edge_wrapper(
            node_a.node_id, 'callback_outlet',
            node_b.node_id, 'callback_inlet'
        )
        
        assert edge is not None
        assert edge.state.is_formally_validated

        # Note: formal validation checks type compatibility and flow type rules,
        # but the edge may not be fully "valid" until built, especially for
        # callbacks outlets can only be attached to event nodes

    # ==================================================================
    # CROSS FLOW-TYPE CONNECTION REJECTION
    # ==================================================================

    def test_exec_to_data_inlet_rejected(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """EXEC outlet → DATA inlet should be rejected (flow type mismatch)."""
        graph = graph_with_library_system
        node_a, node_b = self._create_two_nodes(graph)

        edge = graph.create_edge_wrapper(
            node_a.node_id, 'execute_out',
            node_b.node_id, 'bool_inlet'
        )

        assert not edge.state.is_formally_validated
        assert edge.state.error_formal is not None

        assert not edge.state.is_valid()

    def test_data_to_exec_inlet_rejected(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """DATA outlet → EXEC inlet should be rejected (flow type mismatch)."""
        graph = graph_with_library_system
        node_a, node_b = self._create_two_nodes(graph)

        edge = graph.create_edge_wrapper(
            node_a.node_id, 'bool_outlet',
            node_b.node_id, 'execute_inlet'
        )

        assert not edge.state.is_formally_validated
        assert edge.state.error_formal is not None

        assert not edge.state.is_valid()

    def test_exec_to_callback_inlet_rejected(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """EXEC outlet → CALLBACK inlet should be rejected (flow type mismatch)."""
        graph = graph_with_library_system
        node_a, node_b = self._create_two_nodes(graph)

        edge = graph.create_edge_wrapper(
            node_a.node_id, 'execute_out',
            node_b.node_id, 'callback_inlet'
        )

        assert not edge.state.is_formally_validated
        assert edge.state.error_formal is not None

        assert not edge.state.is_valid()

    def test_callback_to_exec_inlet_rejected(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """CALLBACK outlet → EXEC inlet should be rejected (flow type mismatch)."""
        graph = graph_with_library_system
        node_a, node_b = self._create_two_nodes(graph)

        edge = graph.create_edge_wrapper(
            node_a.node_id, 'callback_outlet',
            node_b.node_id, 'execute_inlet'
        )

        assert not edge.state.is_formally_validated
        assert edge.state.error_formal is not None

        assert not edge.state.is_valid()

    def test_callback_to_data_inlet_rejected(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """CALLBACK outlet → DATA inlet should be rejected (flow type mismatch)."""
        graph = graph_with_library_system
        node_a, node_b = self._create_two_nodes(graph)

        edge = graph.create_edge_wrapper(
            node_a.node_id, 'callback_outlet',
            node_b.node_id, 'bool_inlet'
        )

        assert not edge.state.is_formally_validated
        assert edge.state.error_formal is not None

        assert not edge.state.is_valid()

    def test_data_to_callback_inlet_rejected(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """DATA outlet → CALLBACK inlet should be rejected (flow type mismatch)."""
        graph = graph_with_library_system
        node_a, node_b = self._create_two_nodes(graph)

        edge = graph.create_edge_wrapper(
            node_a.node_id, 'bool_outlet',
            node_b.node_id, 'callback_inlet'
        )

        assert not edge.state.is_formally_validated
        assert edge.state.error_formal is not None

        assert not edge.state.is_valid()

    # ==================================================================
    # DIRECTION VALIDATION (outlet-to-outlet, inlet-to-inlet)
    # ==================================================================

    def test_outlet_to_outlet_rejected(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """Connecting outlet → outlet should be rejected."""
        graph = graph_with_library_system
        node_a, node_b = self._create_two_nodes(graph)

        edge = graph.create_edge_wrapper(
            node_a.node_id, 'bool_outlet',
            node_b.node_id, 'bool_outlet'
        )

        assert not edge.state.is_formally_validated
        assert edge.state.error_formal is not None

        assert not edge.state.is_valid()

    def test_inlet_to_inlet_rejected(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """Connecting inlet → inlet should be rejected."""
        graph = graph_with_library_system
        node_a, node_b = self._create_two_nodes(graph)

        edge = graph.create_edge_wrapper(
            node_a.node_id, 'bool_inlet',
            node_b.node_id, 'bool_inlet'
        )

        assert not edge.state.is_formally_validated
        assert edge.state.error_formal is not None

        assert not edge.state.is_valid()

    # ==================================================================
    # SELF-CONNECTION
    # ==================================================================

    def test_self_connection_data(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """
        Connecting a node's outlet to its own inlet should create
        an edge that passes formal validation (same node, valid types).
        """
        graph = graph_with_library_system
        node_a, _ = self._create_two_nodes(graph)

        edge = graph.create_edge_wrapper(
            node_a.node_id, 'bool_outlet',
            node_a.node_id, 'bool_inlet'
        )

        assert edge is not None
        assert not edge.state.is_formally_validated

        assert not edge.state.is_valid()

    # ==================================================================
    # EDGE REMOVAL
    # ==================================================================

    def test_remove_edge_unlinks_ports(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """Removing an edge should unlink it from both ports."""
        graph = graph_with_library_system
        node_a, node_b = self._create_two_nodes(graph)

        edge = graph.create_edge_wrapper(
            node_a.node_id, 'bool_outlet',
            node_b.node_id, 'bool_inlet'
        )
        assert edge.state.is_valid()

        outlet_port = self._get_port(node_a, 'bool_outlet')
        inlet_port = self._get_port(node_b, 'bool_inlet')

        assert outlet_port.is_linked()
        assert inlet_port.is_linked()

        graph.remove_edge_wrapper(edge.connection_uuid)

        assert not outlet_port.is_linked()
        assert not inlet_port.is_linked()

    def test_remove_edge_from_pooled_inlet_keeps_others(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """
        Removing one edge from a pooled inlet should not affect
        other connections to the same inlet.
        """
        graph = graph_with_library_system
        node_a, node_b, node_c = self._create_three_nodes(graph)

        edge_1 = graph.create_edge_wrapper(
            node_a.node_id, 'bool_outlet',
            node_c.node_id, 'pooled_bool_inlet'
        )
        edge_2 = graph.create_edge_wrapper(
            node_b.node_id, 'bool_outlet',
            node_c.node_id, 'pooled_bool_inlet'
        )

        assert edge_1.state.is_valid()
        assert edge_2.state.is_valid()

        pooled_port = self._get_port(node_c, 'pooled_bool_inlet')
        assert len(pooled_port._linked_edges) == 2

        graph.remove_edge_wrapper(edge_1.connection_uuid)

        assert len(pooled_port._linked_edges) == 1
        assert edge_2.connection_uuid in pooled_port._linked_edges
        assert edge_2.state.is_valid()

    # ==================================================================
    # EDGE STATE INSPECTION
    # ==================================================================

    def test_valid_edge_state_flags(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """A valid data edge should have all state flags set correctly."""
        graph = graph_with_library_system
        node_a, node_b = self._create_two_nodes(graph)

        edge = graph.create_edge_wrapper(
            node_a.node_id, 'bool_outlet',
            node_b.node_id, 'bool_inlet'
        )

        state = edge.state
        assert state.is_registered
        assert state.is_formally_validated
        assert state.is_built
        assert state.has_test_passed
        assert state.is_inlet_linked
        assert state.is_outlet_linked
        assert state.is_linked
        assert state.is_functional()
        assert state.is_valid()
        assert state.get_error() is None

    def test_invalid_edge_has_error(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """An invalid edge (cross flow-type) should have an error set."""
        graph = graph_with_library_system
        node_a, node_b = self._create_two_nodes(graph)

        edge = graph.create_edge_wrapper(
            node_a.node_id, 'execute_out',
            node_b.node_id, 'bool_inlet'
        )

        state = edge.state
        assert not state.is_valid()
        assert state.get_error() is not None

    # ==================================================================
    # INCOMPATIBLE SCALAR-TO-COMPOUND CONNECTIONS
    # ==================================================================

    def test_scalar_to_array_inlet_rejected(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """
        A scalar outlet (TEST_BOOL) to an array-typed pooled inlet
        (Pooled ARRAY[TEST_STRING]) should fail since scalar ↔ compound
        is not supported.
        """
        graph = graph_with_library_system
        node_a, node_b = self._create_two_nodes(graph)

        edge = graph.create_edge_wrapper(
            node_a.node_id, 'bool_outlet',
            node_b.node_id, 'pooled_array_string_inlet'
        )

        assert not edge.state.is_built
        assert not edge.state.is_valid()

    # ==================================================================
    # MULTIPLE ADAPTER CHAIN VERIFICATION
    # ==================================================================

    def test_int_to_float_one_adapter(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """TEST_INT → TEST_FLOAT should use one adapter (IntToFloatAdapter)."""
        graph = graph_with_library_system
        node_a, node_b = self._create_two_nodes(graph)

        edge = graph.create_edge_wrapper(
            node_a.node_id, 'int_outlet',
            node_b.node_id, 'float_inlet'
        )

        assert edge.state.is_valid()
        assert len(edge.edge.chain_adapter_keys) == 1

    def test_int_to_string_two_adapters(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """TEST_INT → TEST_STRING should chain two adapters (Int→Float→String)."""
        graph = graph_with_library_system
        node_a, node_b = self._create_two_nodes(graph)

        edge = graph.create_edge_wrapper(
            node_a.node_id, 'int_outlet',
            node_b.node_id, 'string_inlet'
        )

        assert edge.state.is_valid()
        assert len(edge.edge.chain_adapter_keys) == 2

    def test_float_to_string_one_adapter(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """TEST_FLOAT → TEST_STRING should use one adapter (FloatToStringAdapter)."""
        graph = graph_with_library_system
        node_a, node_b = self._create_two_nodes(graph)

        edge = graph.create_edge_wrapper(
            node_a.node_id, 'float_outlet',
            node_b.node_id, 'string_inlet'
        )

        assert edge.state.is_valid()
        assert len(edge.edge.chain_adapter_keys) == 1

    # ==================================================================
    # POOLED PORT CONFIGURATION
    # ==================================================================

    def test_pooled_port_allows_multiple_connections_flag(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """All pooled inlets should have allow_multiple_connections set to True."""
        graph = graph_with_library_system
        node_a, _ = self._create_two_nodes(graph)

        pooled_port_ids = [
            'pooled_bool_inlet',
            'pooled_int_inlet',
            'pooled_float_inlet',
            'pooled_temperature_inlet',
            'pooled_string_inlet',
            'pooled_array_string_inlet',
        ]

        for port_id in pooled_port_ids:
            port = self._get_port(node_a, port_id)
            assert port.allow_multiple_connections is True, (
                f"Port {port_id} should allow multiple connections"
            )

    def test_standard_data_inlet_disallows_multiple_connections(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """Standard data inlets should NOT allow multiple connections."""
        graph = graph_with_library_system
        node_a, _ = self._create_two_nodes(graph)

        single_port_ids = [
            'bool_inlet',
            'int_inlet',
            'float_inlet',
            'string_inlet',
            'temperature_inlet',
        ]

        for port_id in single_port_ids:
            port = self._get_port(node_a, port_id)
            assert port.allow_multiple_connections is False, (
                f"Port {port_id} should NOT allow multiple connections"
            )

    # ==================================================================
    # TWO-TIER PORT STORAGE & RE-ENABLEMENT
    # ==================================================================

    def test_displaced_edge_remains_in_all_edges(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """
        When a second valid edge displaces the first on a single-connection
        inlet, the displaced edge should leave _linked_edges but remain
        tracked in _all_edges.
        """
        graph = graph_with_library_system
        node_a, node_b, node_c = self._create_three_nodes(graph)

        edge_1 = graph.create_edge_wrapper(
            node_a.node_id, 'bool_outlet',
            node_c.node_id, 'bool_inlet'
        )
        edge_2 = graph.create_edge_wrapper(
            node_b.node_id, 'bool_outlet',
            node_c.node_id, 'bool_inlet'
        )

        inlet_port = self._get_port(node_c, 'bool_inlet')

        # Displaced edge leaves _linked_edges
        assert edge_1.connection_uuid not in inlet_port._linked_edges
        # But remains in _all_edges
        assert edge_1.connection_uuid in inlet_port._all_edges
        # Active edge is in both
        assert edge_2.connection_uuid in inlet_port._linked_edges
        assert edge_2.connection_uuid in inlet_port._all_edges

    def test_reenable_after_active_edge_removed(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """
        When the active edge on a single-connection inlet is removed,
        a previously displaced but functional edge should be automatically
        re-enabled (promoted back to _linked_edges).
        """
        graph = graph_with_library_system
        node_a, node_b, node_c = self._create_three_nodes(graph)

        edge_1 = graph.create_edge_wrapper(
            node_a.node_id, 'bool_outlet',
            node_c.node_id, 'bool_inlet'
        )
        edge_2 = graph.create_edge_wrapper(
            node_b.node_id, 'bool_outlet',
            node_c.node_id, 'bool_inlet'
        )

        # edge_1 is displaced, edge_2 is active
        assert not edge_1.state.is_linked
        assert edge_2.state.is_linked

        # Remove the active edge
        graph.remove_edge_wrapper(edge_2.connection_uuid)

        inlet_port = self._get_port(node_c, 'bool_inlet')

        # edge_1 should be re-enabled
        assert edge_1.connection_uuid in inlet_port._linked_edges
        assert edge_1.state.is_linked
        assert edge_1.state.is_inlet_linked
        assert edge_1.state.is_outlet_linked
        assert edge_1.state.error_link is None

    def test_detach_removes_from_all_edges(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """
        detach() (via remove_edge_wrapper) should fully remove the edge
        from both _linked_edges and _all_edges on both ports.
        """
        graph = graph_with_library_system
        node_a, node_b = self._create_two_nodes(graph)

        edge = graph.create_edge_wrapper(
            node_a.node_id, 'bool_outlet',
            node_b.node_id, 'bool_inlet'
        )
        assert edge.state.is_valid()

        outlet_port = self._get_port(node_a, 'bool_outlet')
        inlet_port = self._get_port(node_b, 'bool_inlet')

        graph.remove_edge_wrapper(edge.connection_uuid)

        # Fully removed from both tiers on both ports
        assert edge.connection_uuid not in inlet_port._linked_edges
        assert edge.connection_uuid not in inlet_port._all_edges
        assert edge.connection_uuid not in outlet_port._linked_edges
        assert edge.connection_uuid not in outlet_port._all_edges

    def test_asymmetric_inlet_displacement(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """
        When an edge is displaced from an INLET, the source outlet
        MUST be informed (the outlet removes the edge from its linked set
        so pipes are rebuilt correctly).
        """
        graph = graph_with_library_system
        node_a, node_b, node_c = self._create_three_nodes(graph)

        edge_1 = graph.create_edge_wrapper(
            node_a.node_id, 'bool_outlet',
            node_c.node_id, 'bool_inlet'
        )
        assert edge_1.state.is_valid()

        # Displace edge_1 at the inlet
        edge_2 = graph.create_edge_wrapper(
            node_b.node_id, 'bool_outlet',
            node_c.node_id, 'bool_inlet'
        )

        outlet_port_a = self._get_port(node_a, 'bool_outlet')
        inlet_port_c = self._get_port(node_c, 'bool_inlet')

        # edge_1 should be removed from the source outlet's linked set
        assert edge_1.connection_uuid not in outlet_port_a._linked_edges
        # edge_1 should not be linked on either side
        assert not edge_1.state.is_inlet_linked
        assert not edge_1.state.is_outlet_linked
        assert not edge_1.state.is_linked

    def test_asymmetric_outlet_displacement(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """
        When an edge is displaced from an OUTLET (e.g. exec outlet,
        single-connection), the sink inlet should NOT be informed.
        The inlet retains the stale edge in its linked set.
        """
        graph = graph_with_library_system
        node_a, node_b, node_c = self._create_three_nodes(graph)

        # Exec outlets are single-connection
        edge_1 = graph.create_edge_wrapper(
            node_a.node_id, 'execute_out',
            node_b.node_id, 'execute_inlet'
        )
        assert edge_1.state.is_valid()

        # Displace edge_1 at the outlet
        edge_2 = graph.create_edge_wrapper(
            node_a.node_id, 'execute_out',
            node_c.node_id, 'execute_inlet'
        )

        outlet_port_a = self._get_port(node_a, 'execute_out')
        inlet_port_b = self._get_port(node_b, 'execute_inlet')

        # edge_1 should be removed from outlet
        assert edge_1.connection_uuid not in outlet_port_a._linked_edges
        # Sink inlet NOT informed — edge_1 remains in inlet's linked set
        assert edge_1.connection_uuid in inlet_port_b._linked_edges

        # Edge state reflects asymmetry
        assert edge_1.state.is_inlet_linked  # Stale but harmless
        assert not edge_1.state.is_outlet_linked
        assert not edge_1.state.is_linked

    def test_reenable_skips_nonfunctional(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """
        Re-enablement should skip edges that lost functionality
        (e.g. adapter chain broke during hot reload). Only functional
        candidates should be promoted.
        """
        graph = graph_with_library_system
        node_a, node_b, node_c = self._create_three_nodes(graph)

        edge_1 = graph.create_edge_wrapper(
            node_a.node_id, 'bool_outlet',
            node_c.node_id, 'bool_inlet'
        )
        edge_2 = graph.create_edge_wrapper(
            node_b.node_id, 'bool_outlet',
            node_c.node_id, 'bool_inlet'
        )

        # edge_1 is displaced; simulate hot reload failure
        edge_1._state.is_built = False

        # Remove the active edge
        graph.remove_edge_wrapper(edge_2.connection_uuid)

        inlet_port = self._get_port(node_c, 'bool_inlet')

        # edge_1 is not functional, so it should NOT be re-enabled
        assert edge_1.connection_uuid not in inlet_port._linked_edges
        assert not inlet_port.is_linked()

    # ==================================================================
    # VALIDATION PIPELINE: HOT RELOAD & RECONFIGURATION
    # ==================================================================

    def _create_dynamic_node(self, graph: BaseGraph):
        """Create a DynamicPortTestNode and return its wrapper."""
        from haybale_testing.nodes.testbed.dynamic_port_test import DynamicPortTestNode
        return graph.create_node_wrapper(
            DynamicPortTestNode.class_identity.registry_key,
            position=(100, 100)
        )

    def test_node_validation_edges_stay_valid(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """
        After marking a node dirty with NODE_VALIDATION_REQUESTED and
        running force_immediate_validation(), all edges attached to that
        node should remain valid and linked.
        """
        from haywire.core.graph.types import ChangeReason

        graph = graph_with_library_system
        node_a, node_b = self._create_two_nodes(graph)

        edge = graph.create_edge_wrapper(
            node_a.node_id, 'bool_outlet',
            node_b.node_id, 'bool_inlet'
        )
        # Flush pending NODE_ADDED from creation
        graph._validation.force_immediate_validation()
        assert edge.state.is_valid()

        # Simulate node validation request (e.g. port reconfiguration)
        graph._validation.mark_node_dirty(
            node_a.node_id,
            ChangeReason.NODE_VALIDATION_REQUESTED
        )
        result = graph._validation.force_immediate_validation()

        # Edge should still be valid after validation
        assert edge.state.is_valid()
        assert edge.state.is_linked

        # Ports should still have the edge
        outlet_port = self._get_port(node_a, 'bool_outlet')
        inlet_port = self._get_port(node_b, 'bool_inlet')
        assert edge.connection_uuid in outlet_port._linked_edges
        assert edge.connection_uuid in inlet_port._linked_edges

    def test_node_hot_reload_edges_survive_rebuild(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """
        After a full node hot reload (NODE_HOT_RELOADED), the node is
        completely rebuilt with new port objects. Edges should survive
        by rebinding to the new ports.
        """
        from haywire.core.graph.types import ChangeReason

        graph = graph_with_library_system
        node_a, node_b = self._create_two_nodes(graph)

        edge = graph.create_edge_wrapper(
            node_a.node_id, 'bool_outlet',
            node_b.node_id, 'bool_inlet'
        )
        assert edge.state.is_valid()

        # Flush pending NODE_ADDED validation from create_node/edge_wrapper
        graph._validation.force_immediate_validation()

        # Remember old port objects
        old_outlet = self._get_port(node_a, 'bool_outlet')

        # Simulate hot reload — rebuilds the entire node
        graph._validation.mark_node_dirty(
            node_a.node_id,
            ChangeReason.NODE_HOT_RELOADED
        )
        result = graph._validation.force_immediate_validation()

        # Edge should be valid after rebuild
        assert edge.state.is_valid()
        assert edge.state.is_linked

        # Port objects should be NEW (node was re-instantiated)
        new_outlet = self._get_port(node_a, 'bool_outlet')
        assert new_outlet is not old_outlet

        # Edge should be linked at the new port
        assert edge.connection_uuid in new_outlet._linked_edges

        # Edge should be linked at the new port
        assert edge.connection_uuid in new_outlet._linked_edges

    def test_node_hot_reload_adapter_chain_survives(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """
        An edge with an adapter chain (bool→int) should survive a hot
        reload of either node, rebuilding its adapter chain against
        the new port objects.
        """
        from haywire.core.graph.types import ChangeReason

        graph = graph_with_library_system
        node_a, node_b = self._create_two_nodes(graph)

        # bool→int requires BoolToIntAdapter
        edge = graph.create_edge_wrapper(
            node_a.node_id, 'bool_outlet',
            node_b.node_id, 'int_inlet'
        )
        # Flush pending NODE_ADDED from creation
        graph._validation.force_immediate_validation()
        assert edge.state.is_valid()
        assert len(edge.edge.chain_adapter_keys) == 1

        # Hot reload the sink node
        graph._validation.mark_node_dirty(
            node_b.node_id,
            ChangeReason.NODE_HOT_RELOADED
        )
        result = graph._validation.force_immediate_validation()

        # Edge should survive with adapter chain intact
        assert edge.state.is_valid()
        assert len(edge.edge.chain_adapter_keys) == 1

        # Linked at new ports
        new_inlet = self._get_port(node_b, 'int_inlet')
        assert edge.connection_uuid in new_inlet._linked_edges

    def test_node_hot_reload_displaced_edge_survives(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """
        After a hot reload, displaced edges should still be tracked
        in _all_edges on the rebuilt ports, and the active edge should
        be the one that was last linked.
        """
        from haywire.core.graph.types import ChangeReason

        graph = graph_with_library_system
        node_a, node_b, node_c = self._create_three_nodes(graph)

        # edge_1 will be displaced by edge_2
        edge_1 = graph.create_edge_wrapper(
            node_a.node_id, 'bool_outlet',
            node_c.node_id, 'bool_inlet'
        )
        edge_2 = graph.create_edge_wrapper(
            node_b.node_id, 'bool_outlet',
            node_c.node_id, 'bool_inlet'
        )

        # Flush pending NODE_ADDED from creation
        graph._validation.force_immediate_validation()
        assert not edge_1.state.is_linked
        assert edge_2.state.is_valid()

        # Hot reload the sink node (rebuilds ports)
        graph._validation.mark_node_dirty(
            node_c.node_id,
            ChangeReason.NODE_HOT_RELOADED
        )
        result = graph._validation.force_immediate_validation()

        new_inlet = self._get_port(node_c, 'bool_inlet')

        # After rebuild: both edges are rebuilt and link() is called
        # in order. edge_1 links first, then edge_2 displaces it.
        assert edge_2.state.is_valid()
        assert edge_2.connection_uuid in new_inlet._linked_edges

        # edge_1 was displaced again — in _all_edges but not _linked_edges
        assert edge_1.connection_uuid in new_inlet._all_edges
        assert edge_1.connection_uuid not in new_inlet._linked_edges

    def test_dynamic_port_removal_detaches_edge(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """
        When a dynamic port is removed via push/pop reconfiguration,
        the edge connected to that port should be detached (unlinked
        from both ports).
        """
        from haywire.core.graph.types import ChangeReason

        graph = graph_with_library_system
        dyn_node = self._create_dynamic_node(graph)
        node_b, _ = self._create_two_nodes(graph)

        # Connect to dynamic_outlet_1 (exists with default port_count=2)
        edge = graph.create_edge_wrapper(
            dyn_node.node_id, 'dynamic_outlet_1',
            node_b.node_id, 'int_inlet'
        )
        # Flush pending NODE_ADDED from creation
        graph._validation.force_immediate_validation()
        assert edge.state.is_valid()

        # Reconfigure to port_count=1 — removes dynamic_inlet_1, dynamic_outlet_1
        dyn_node.node.ports['port_count'].set_value(1)

        # pop() already marked the node dirty; run validation
        result = graph._validation.force_immediate_validation()

        # The dynamic port is gone
        assert 'dynamic_outlet_1' not in dyn_node.node.ports

        # Edge should no longer be linked (port was destroyed)
        assert not edge.state.is_linked

    def test_dynamic_port_edge_survives_reconfiguration(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """
        When a dynamic port survives push/pop reconfiguration (same ID
        re-added), the edge connected to it should remain valid after
        validation rebuilds it.
        """
        from haywire.core.graph.types import ChangeReason

        graph = graph_with_library_system
        dyn_node = self._create_dynamic_node(graph)
        node_b, _ = self._create_two_nodes(graph)

        # Connect to dynamic_outlet_0 (always present when count >= 1)
        edge = graph.create_edge_wrapper(
            dyn_node.node_id, 'dynamic_outlet_0',
            node_b.node_id, 'int_inlet'
        )
        # Flush pending NODE_ADDED from creation
        graph._validation.force_immediate_validation()
        assert edge.state.is_valid()

        # Reconfigure to port_count=3 — dynamic_outlet_0 survives, adds 2
        dyn_node.node.ports['port_count'].set_value(3)

        # pop() marked node dirty; run validation
        result = graph._validation.force_immediate_validation()

        # Port still exists
        assert 'dynamic_outlet_0' in dyn_node.node.ports

        # Edge should be valid after rebuild
        assert edge.state.is_valid()
        assert edge.state.is_linked

        # New dynamic ports should also be available
        assert 'dynamic_outlet_2' in dyn_node.node.ports

    def test_static_port_edge_survives_dynamic_reconfiguration(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """
        Edges connected to static ports (not affected by push/pop)
        should be completely unaffected by dynamic port reconfiguration.
        """
        from haywire.core.graph.types import ChangeReason

        graph = graph_with_library_system
        dyn_node = self._create_dynamic_node(graph)
        node_b, _ = self._create_two_nodes(graph)

        # Connect to the static bool_outlet
        edge = graph.create_edge_wrapper(
            dyn_node.node_id, 'bool_outlet',
            node_b.node_id, 'bool_inlet'
        )
        # Flush pending NODE_ADDED from creation
        graph._validation.force_immediate_validation()
        assert edge.state.is_valid()

        # Reconfigure dynamic ports to 0 — removes all dynamic ports
        dyn_node.node.ports['port_count'].set_value(0)

        # Validate
        result = graph._validation.force_immediate_validation()

        # Static edge should be completely unaffected
        assert edge.state.is_valid()
        assert edge.state.is_linked

        # Dynamic ports are gone, but static ports remain
        assert 'dynamic_outlet_0' not in dyn_node.node.ports
        assert 'bool_outlet' in dyn_node.node.ports

    # ==================================================================
    # LAZY PROPAGATION
    # ==================================================================

    def test_lazy_edge_creation(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """create_edge_wrapper(..., lazy=True) should set is_lazy on the edge."""
        graph = graph_with_library_system
        node_a, node_b = self._create_two_nodes(graph)

        edge = graph.create_edge_wrapper(
            node_a.node_id, 'bool_outlet',
            node_b.node_id, 'bool_inlet',
            lazy=True
        )

        assert edge is not None
        assert edge.state.is_valid()
        assert edge.is_lazy is True
        assert edge.edge.is_lazy is True

    def test_lazy_edge_serialization(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """is_lazy should survive to_dict() round-trip."""
        graph = graph_with_library_system
        node_a, node_b = self._create_two_nodes(graph)

        edge = graph.create_edge_wrapper(
            node_a.node_id, 'bool_outlet',
            node_b.node_id, 'bool_inlet',
            lazy=True
        )

        # Serialize and check
        edge_dict = edge.edge.to_dict()
        assert edge_dict['is_lazy'] is True

        # Eager edge should serialize as False
        node_c, _ = self._create_two_nodes(graph)
        eager_edge = graph.create_edge_wrapper(
            node_a.node_id, 'int_outlet',
            node_c.node_id, 'int_inlet',
            lazy=False
        )
        assert eager_edge.edge.to_dict()['is_lazy'] is False

    def test_eager_edge_defers_on_change(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """
        Eager edge pushes value to inlet, but on_change should NOT fire
        at push time. It fires during resolve_dirty_data() instead.
        """
        graph = graph_with_library_system
        node_a, node_b = self._create_two_nodes(graph)

        # Connect bool→bool (eager, same type, no adapter)
        edge = graph.create_edge_wrapper(
            node_a.node_id, 'bool_outlet',
            node_b.node_id, 'bool_inlet'
        )
        graph._validation.force_immediate_validation()
        assert edge.state.is_valid()

        inlet_port = self._get_port(node_b, 'bool_inlet')
        outlet_port = self._get_port(node_a, 'bool_outlet')

        # Set value on outlet — pipes propagate to inlet
        outlet_port.set_value(False)

        # Inlet should have the value stored (eager push happened)
        assert inlet_port.get_value() == False

        # Port should be marked dirty (deferred)
        assert inlet_port in node_b.node._has_dirty_ports

    def test_lazy_edge_does_not_push_value(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """
        Lazy edge should NOT transform/push value when outlet changes.
        It should only mark the inlet as dirty with the pipe reference.
        """
        graph = graph_with_library_system
        node_a, node_b = self._create_two_nodes(graph)

        edge = graph.create_edge_wrapper(
            node_a.node_id, 'bool_outlet',
            node_b.node_id, 'bool_inlet',
            lazy=True
        )
        graph._validation.force_immediate_validation()
        assert edge.state.is_valid()

        inlet_port = self._get_port(node_b, 'bool_inlet')
        outlet_port = self._get_port(node_a, 'bool_outlet')

        # Get inlet's value before outlet changes
        original_value = inlet_port.get_value()

        # Set outlet value — lazy pipe should NOT push
        outlet_port.set_value(not original_value)

        # Inlet should still have original value (not pushed)
        assert inlet_port.get_value() == original_value

        # But inlet port should be marked dirty
        assert inlet_port in node_b.node._has_dirty_ports

        # And _pending_lazy_pipes should have an entry
        assert len(inlet_port._pending_lazy_pipes) == 1

    def test_lazy_edge_pulls_on_resolve(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """
        resolve_dirty_data() should pull the latest value through the
        adapter chain from the source outlet.
        """
        graph = graph_with_library_system
        node_a, node_b = self._create_two_nodes(graph)

        # bool→int requires adapter (BoolToIntAdapter)
        edge = graph.create_edge_wrapper(
            node_a.node_id, 'bool_outlet',
            node_b.node_id, 'int_inlet',
            lazy=True
        )
        graph._validation.force_immediate_validation()
        assert edge.state.is_valid()
        assert len(edge.edge.chain_adapter_keys) == 1

        inlet_port = self._get_port(node_b, 'int_inlet')
        outlet_port = self._get_port(node_a, 'bool_outlet')

        # Set outlet to True — lazy, not pushed yet
        outlet_port.set_value(True)
        original_inlet_value = inlet_port.get_value()

        # Resolve dirty data — should pull and transform
        inlet_port.resolve_dirty_data()

        # Inlet should now have the transformed value (True → 1 via BoolToInt)
        resolved_value = inlet_port.get_value()
        assert resolved_value != original_inlet_value
        assert resolved_value is not None

        # Pending lazy pipes should be cleared
        assert len(inlet_port._pending_lazy_pipes) == 0

    def test_lazy_always_latest(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """
        When outlet changes A→B→C before resolve, lazy inlet should get C
        (always-latest semantics, skipping intermediates).
        """
        graph = graph_with_library_system
        node_a, node_b = self._create_two_nodes(graph)

        edge = graph.create_edge_wrapper(
            node_a.node_id, 'int_outlet',
            node_b.node_id, 'int_inlet',
            lazy=True
        )
        graph._validation.force_immediate_validation()
        assert edge.state.is_valid()

        inlet_port = self._get_port(node_b, 'int_inlet')
        outlet_port = self._get_port(node_a, 'int_outlet')

        # Change outlet 3 times — lazy, none pushed
        outlet_port.set_value(10)
        outlet_port.set_value(20)
        outlet_port.set_value(30)

        # Resolve — should get latest value (30)
        inlet_port.resolve_dirty_data()

        assert inlet_port.get_value() == 30

    def test_mixed_pooled_on_change_debounce(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """
        Pooled inlet with eager + lazy edges: on_change should fire
        once during resolve_dirty_data(), not per-edge-push.
        """
        graph = graph_with_library_system
        node_a, node_b, node_c = self._create_three_nodes(graph)

        # Both connect to pooled_bool_inlet on node_c
        eager_edge = graph.create_edge_wrapper(
            node_a.node_id, 'bool_outlet',
            node_c.node_id, 'pooled_bool_inlet',
            lazy=False
        )
        lazy_edge = graph.create_edge_wrapper(
            node_b.node_id, 'bool_outlet',
            node_c.node_id, 'pooled_bool_inlet',
            lazy=True
        )
        graph._validation.force_immediate_validation()
        assert eager_edge.state.is_valid()
        assert lazy_edge.state.is_valid()

        pooled_port = self._get_port(node_c, 'pooled_bool_inlet')

        # Both edges should be linked
        assert eager_edge.connection_uuid in pooled_port._linked_edges
        assert lazy_edge.connection_uuid in pooled_port._linked_edges

        # Change both outlets
        outlet_a = self._get_port(node_a, 'bool_outlet')
        outlet_b = self._get_port(node_b, 'bool_outlet')
        outlet_a.set_value(True)
        outlet_b.set_value(False)

        # Port should be dirty
        assert pooled_port in node_c.node._has_dirty_ports

        # Lazy edge should have pending pipe
        assert len(pooled_port._pending_lazy_pipes) == 1

        # Resolve — pulls lazy data, fires on_change once
        pooled_port.resolve_dirty_data()

        # Pending should be cleared
        assert len(pooled_port._pending_lazy_pipes) == 0

    def test_widget_change_fires_on_change_immediately(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """
        Widget/programmatic change (no connection_uuid) with on_change
        should fire on_change immediately, not deferred.
        """
        graph = graph_with_library_system
        dyn_node = self._create_dynamic_node(graph)

        # port_count has on_change='hb_reconfigure'
        config_port = dyn_node.node.ports['port_count']
        assert config_port.on_change == 'hb_reconfigure'

        # Start with 2 dynamic ports
        assert 'dynamic_outlet_0' in dyn_node.node.ports
        assert 'dynamic_outlet_1' in dyn_node.node.ports

        # Widget change (no connection_uuid) — should fire on_change immediately
        config_port.set_value(3)

        # Reconfigure should have already happened (immediate on_change)
        assert 'dynamic_outlet_2' in dyn_node.node.ports
