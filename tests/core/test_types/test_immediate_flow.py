"""Which wire roles are immediate, and which ports cache it."""

import pytest


@pytest.mark.unit
def test_only_the_callback_wire_type_is_immediate():
    from haywire.barn.builtin.wires import CallbackWire, ControlWire, DataWire
    from haywire.core.types import WireRole

    assert CallbackWire.role is WireRole.IMMEDIATE
    assert DataWire.role is not WireRole.IMMEDIATE
    assert ControlWire.role is not WireRole.IMMEDIATE


@pytest.mark.integration
class TestPortsCacheImmediacy:
    def test_a_callback_outlet_is_immediate(self, graph_with_library_system, library_system):
        from haybale_testing.nodes.testbed.custom_callback_node import TestCustomCallbackNode

        event = graph_with_library_system.create_node_wrapper(
            TestCustomCallbackNode.class_identity.registry_key, position=(0, 0)
        )

        assert event.node.ports["listen_callback"].is_immediate

    def test_a_pooled_callback_inlet_is_immediate(self, graph_with_library_system, library_system):
        """A pooled port's wire type is its element's; the cache follows it."""
        from haybale_testing.nodes.testbed.emit_callback_node import TestEmitCallbackNode

        emit = graph_with_library_system.create_node_wrapper(
            TestEmitCallbackNode.class_identity.registry_key, position=(0, 0)
        )

        assert emit.node.ports["edge_callback"].is_immediate

    def test_a_data_inlet_is_not_immediate(self, graph_with_library_system, library_system):
        from haybale_testing.nodes.testbed.math_op_node import TestAddFloatNode

        add = graph_with_library_system.create_node_wrapper(
            TestAddFloatNode.class_identity.registry_key, position=(0, 0)
        )

        assert not add.node.ports["value_a"].is_immediate

    def test_an_edge_into_a_pooled_callback_inlet_fires_on_change_at_once(
        self, graph_with_library_system, library_system
    ):
        from haybale_testing.nodes.testbed.custom_callback_node import TestCustomCallbackNode
        from haybale_testing.nodes.testbed.emit_callback_node import TestEmitCallbackNode

        graph = graph_with_library_system
        event = graph.create_node_wrapper(
            TestCustomCallbackNode.class_identity.registry_key, position=(0, 0)
        )
        emit = graph.create_node_wrapper(TestEmitCallbackNode.class_identity.registry_key, position=(300, 0))
        emit.node.callback_index = 5  # the inlet's on_change handler, printout(), resets it to 0

        graph.create_edge_wrapper(event.node_id, "listen_callback", emit.node_id, "edge_callback")

        assert emit.node.callback_index == 0
