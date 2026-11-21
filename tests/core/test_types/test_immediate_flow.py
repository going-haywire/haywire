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
        from haybale_testing.nodes.testbed.callback_event_probe import CallbackEventProbeNode

        event = graph_with_library_system.create_node_wrapper(
            CallbackEventProbeNode.class_identity.registry_key, position=(0, 0)
        )

        assert event.node.ports["listen_callback"].is_immediate

    def test_a_pooled_callback_inlet_is_immediate(self, graph_with_library_system, library_system):
        """A pooled port's wire type is its element's; the cache follows it."""
        from haybale_testing.nodes.testbed.callback_emit_probe import CallbackEmitProbeNode

        emit = graph_with_library_system.create_node_wrapper(
            CallbackEmitProbeNode.class_identity.registry_key, position=(0, 0)
        )

        assert emit.node.ports["edge_callback"].is_immediate

    def test_a_data_inlet_is_not_immediate(self, graph_with_library_system, library_system):
        from haybale_testing.nodes.testbed.add_float_probe import AddFloatProbeNode

        add = graph_with_library_system.create_node_wrapper(
            AddFloatProbeNode.class_identity.registry_key, position=(0, 0)
        )

        assert not add.node.ports["value_a"].is_immediate

    def test_an_edge_into_a_pooled_callback_inlet_fires_on_change_at_once(
        self, graph_with_library_system, library_system
    ):
        from haybale_testing.nodes.testbed.callback_event_probe import CallbackEventProbeNode
        from haybale_testing.nodes.testbed.callback_emit_probe import CallbackEmitProbeNode

        graph = graph_with_library_system
        event = graph.create_node_wrapper(
            CallbackEventProbeNode.class_identity.registry_key, position=(0, 0)
        )
        emit = graph.create_node_wrapper(
            CallbackEmitProbeNode.class_identity.registry_key, position=(300, 0)
        )
        emit.node.callback_index = 5  # the inlet's on_change handler, printout(), resets it to 0

        graph.create_edge_wrapper(event.node_id, "listen_callback", emit.node_id, "edge_callback")

        assert emit.node.callback_index == 0
