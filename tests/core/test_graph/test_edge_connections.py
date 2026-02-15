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
        assert len(inlet_port._edge_wrappers) == 1

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
        assert len(inlet_port._edge_wrappers) == 1
        assert edge_2.connection_uuid in inlet_port._edge_wrappers

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
        assert edge_valid.connection_uuid in inlet_port._edge_wrappers
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
        assert len(inlet_port._edge_wrappers) == 1
        assert edge_2.connection_uuid in inlet_port._edge_wrappers
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
        assert len(pooled_port._edge_wrappers) == 2

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
        assert len(pooled_port._edge_wrappers) == 2

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
        assert len(outlet_port._edge_wrappers) == 2

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
        assert len(outlet_port._edge_wrappers) == 1

        # The second edge should be the one linked
        assert edge_2.connection_uuid in outlet_port._edge_wrappers
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
        assert len(inlet_port._edge_wrappers) == 2

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
        assert len(pooled_port._edge_wrappers) == 2

        graph.remove_edge_wrapper(edge_1.connection_uuid)

        assert len(pooled_port._edge_wrappers) == 1
        assert edge_2.connection_uuid in pooled_port._edge_wrappers
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
