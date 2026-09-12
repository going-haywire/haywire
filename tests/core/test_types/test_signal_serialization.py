"""A node carrying EXEC or CALLBACK pins must survive serialization.

An untouched signal port's field holds ``None``, which ``PrimitiveType`` cannot
construct — so a port asked to store one raises from inside
``PrimitiveField.to_dict``, taking copy and save down with it. The type-level
store strategy is what keeps the question from being asked; see
``tests/barn/test_signal_types.py`` for the strategies themselves.

A CALLBACK port carries the subscription key its listener registers under. A key
declared per port round-trips through the serialized ``default`` kwarg, and one
the node wrote is kept as field data (``StoreStrategy.NODE_SET``).
"""

import pytest

from haywire.core.graph.base import BaseGraph


@pytest.mark.integration
class TestSignalSerialization:
    def test_a_node_with_signal_ports_can_be_serialized(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """The copy path. EdgeLinkTestNode carries a callback and an exec pin per direction."""
        from haybale_testing.nodes.testbed.edge_link_test import EdgeLinkTestNode

        wrapper = graph_with_library_system.create_node_wrapper(
            EdgeLinkTestNode.class_identity.registry_key, position=(0, 0)
        )
        assert wrapper is not None

        ports = wrapper.serialize(include_data=True)["node_data"]["ports"]

        signal_ports = [pid for pid in ports if "callback" in pid or "execute" in pid]
        assert signal_ports
        for pid in signal_ports:
            assert "field_data" not in ports[pid], f"{pid} stored a signal value"

    def test_a_callback_subscription_key_survives_a_round_trip(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """A CALLBACK port carries the key its listener registers under.

        The key is declared per port (``default=self.node_id``), so it travels
        in the serialized ``default`` kwarg and is restored by ``create_field``
        — which is what makes ``StoreStrategy.NEVER`` safe here rather than
        lossy.
        """
        from haybale_core.nodes.events.tick_event import TickEventNode

        graph = graph_with_library_system
        wrapper = graph.create_node_wrapper(TickEventNode.class_identity.registry_key, position=(0, 0))
        assert wrapper is not None
        original = wrapper.node.value("listen_callback")
        assert original == wrapper.node_id

        data = wrapper.serialize(include_data=True)["node_data"]

        restored = graph.create_node_wrapper(TickEventNode.class_identity.registry_key, position=(500, 0))
        assert restored is not None
        restored.node._initialize_from_dict(data)

        assert restored.node.value("listen_callback") == original

    def test_a_node_written_callback_key_survives_a_round_trip(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """``NODE_SET`` keeps a key the node chose at runtime, unlike ``NEVER``."""
        from haybale_core.nodes.events.tick_event import TickEventNode

        graph = graph_with_library_system
        wrapper = graph.create_node_wrapper(TickEventNode.class_identity.registry_key, position=(0, 0))
        assert wrapper is not None
        wrapper.node.out("listen_callback", "chosen_at_runtime")

        data = wrapper.serialize(include_data=True)["node_data"]
        assert "field_data" in data["ports"]["listen_callback"]

        restored = graph.create_node_wrapper(TickEventNode.class_identity.registry_key, position=(500, 0))
        assert restored is not None
        restored.node._initialize_from_dict(data)

        assert restored.node.value("listen_callback") == "chosen_at_runtime"

    def test_a_node_with_signal_ports_can_be_copied(
        self, graph_with_library_system: BaseGraph, library_system
    ):
        """``build_clipboard_payload`` is what the user's copy gesture reaches."""
        from haybale_testing.nodes.testbed.edge_link_test import EdgeLinkTestNode
        from haywire.core.graph.clipboard import build_clipboard_payload

        graph = graph_with_library_system
        wrapper = graph.create_node_wrapper(EdgeLinkTestNode.class_identity.registry_key, position=(0, 0))
        assert wrapper is not None

        payload = build_clipboard_payload(graph, [wrapper.node_id], [], session_id="s")

        assert wrapper.node_id in payload["nodes"]
