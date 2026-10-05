"""A callback port with no subscription is absent: `None`, saved as null, dropped by pools (Q14, Q22)."""

import importlib
from typing import Any, cast

import pytest

from tests.conftest import make_edge, make_node
from tests.core.test_graph.callback_group import EMIT, LISTEN, build_group, subscriptions

pytestmark = pytest.mark.integration


def _split_with_reroute(graph, edge_id: str) -> str:
    """Split *edge_id* with a reroute node the way the canvas does, returning the reroute's id."""
    from haywire.barn.builtin.nodes.reroute import RerouteNode
    from haywire.core.undo.actions.graph_actions import SplitEdgeWithRerouteAction

    action = SplitEdgeWithRerouteAction(
        graph=cast(Any, graph),
        edge_id=edge_id,
        position=(200.0, 0.0),
        registry_key=RerouteNode.class_identity.registry_key,
    )
    action._execute_impl()
    reroute_id = action.reroute_node_id
    assert reroute_id is not None
    return reroute_id


def _port_block(serialized_node: dict, port_id: str) -> dict:
    """The serialized port *port_id* of a node, as `wrapper.serialize()` or `graph.to_dict()` writes it."""
    return serialized_node.get("node_data", serialized_node)["ports"][port_id]


class TestTypes:
    @pytest.mark.parametrize(
        "path",
        ["haywire.barn.builtin.types:CALLBACK", "haybale_testing.types:TEST_RECORD_CALLBACK"],
    )
    def test_a_callback_type_starts_absent(self, library_system, path):
        module, name = path.split(":")
        callback = getattr(importlib.import_module(module), name)

        assert callback.class_identity.default == {}
        assert callback.create_field().get_value() is None


class TestPools:
    def test_absence_from_a_source_removes_its_entry(self, library_system):
        from haybale_core.types import PooledType

        from haywire.barn.builtin.types import CALLBACK

        pool = PooledType[CALLBACK].create_field()
        pool.set_value("a", source_id="e1")
        pool.set_value("b", source_id="e2")

        pool.set_value(None, source_id="e1")

        assert pool.get_value() == {"e2": "b"}
        assert pool.accepts_absence()

    def test_an_empty_name_is_a_subscription(self, library_system):
        from haybale_core.types import PooledType

        from haywire.barn.builtin.types import CALLBACK

        pool = PooledType[CALLBACK].create_field()

        pool.set_value("", source_id="e1")

        assert pool.get_value() == {"e1": ""}

    def test_a_dataclass_with_an_empty_name_is_a_subscription(self, library_system):
        from haybale_core.types import PooledType
        from haybale_testing.types import TEST_RECORD_CALLBACK

        pool = PooledType[TEST_RECORD_CALLBACK].create_field()

        pool.set_value(TEST_RECORD_CALLBACK(), source_id="e1")

        assert pool.get_value() == {"e1": TEST_RECORD_CALLBACK()}

    def test_absence_without_a_source_changes_nothing(self, library_system):
        from haybale_core.types import PooledType

        from haywire.barn.builtin.types import CALLBACK

        pool = PooledType[CALLBACK].create_field()
        pool.set_value("a", source_id="e1")

        pool.set_value(None)

        assert pool.get_value() == {"e1": "a"}

    def test_a_pool_of_data_keeps_a_none_entry(self, library_system):
        from haybale_core.types import PooledType

        from haywire.barn.builtin.types import FLOAT

        pool = PooledType[FLOAT].create_field()
        pool.set_value(1.0, source_id="e1")

        pool.set_value(None, source_id="e1")

        assert not pool.accepts_absence()
        assert pool.get_value() == {"e1": None}


class TestPorts:
    def test_an_unlinked_dataclass_callback_inlet_reads_absent(self, graph_with_library_system):
        from haybale_testing.nodes.testbed.record_callback_nodes import (
            TestRecordEmitNode,
            TestRecordEventNode,
        )

        graph = graph_with_library_system
        event = make_node(graph, TestRecordEventNode.class_identity.registry_key, position=(0, 0))
        emit = make_node(graph, TestRecordEmitNode.class_identity.registry_key, position=(400, 0))
        edge = make_edge(graph, event.node_id, "subscription", emit.node_id, "subscriptions")
        reroute_id = _split_with_reroute(graph, edge.edge_id)
        upstream = next(e for e in graph.edge_wrappers.values() if e.sink_node_id == reroute_id)

        graph.remove_edge_wrapper(upstream.edge_id)

        assert graph.node_wrappers[reroute_id].node.ports["in"].get_value() is None
        assert emit.node.ports["subscriptions"].get_value() == {}


class TestEverySaveGoesThroughTheField:
    """Each path that writes port values writes an absent callback as null and loads it absent."""

    @staticmethod
    def _listener_set_absent(graph):
        listener = make_node(graph, LISTEN, position=(0, 0))
        listener.node.out("listen_callback", None)  # its default is its node id; absence must survive
        return listener

    def test_the_graph_file(self, graph_with_library_system):
        graph = graph_with_library_system
        listener = self._listener_set_absent(graph)
        data = graph.to_dict()
        assert _port_block(data["nodes"][listener.node_id], "listen_callback")["field_data"] is None

        graph.clear()
        graph.load_from_dict(data)

        assert graph.node_wrappers[listener.node_id].node.value("listen_callback") is None

    def test_a_node_copy_and_undo_snapshot(self, graph_with_library_system):
        """Clipboard and the undo actions (Collapse, Expand, Detach, Promote) use `wrapper.serialize`."""
        from haywire.core.graph.clipboard import build_clipboard_payload

        graph = graph_with_library_system
        listener = self._listener_set_absent(graph)
        payload = build_clipboard_payload(graph, [listener.node_id], [], session_id="s")
        node_data = payload["nodes"][listener.node_id]["node_data"]
        assert _port_block(node_data, "listen_callback")["field_data"] is None

        restored = make_node(graph, LISTEN, position=(500, 0))
        restored.node._initialize_from_dict(node_data)

        assert restored.node.value("listen_callback") is None

    def test_a_subgraph_definition(self, graph_with_library_system):
        """`_DropSubgraph` and the clipboard's subgraphs serialize through `definition.to_dict`."""
        group = build_group(graph_with_library_system)
        outlet = group.input_node.node.ports["sub_in"]
        outlet.set_value("a")
        outlet.set_value(None)

        data = group.definition.to_dict(include_data=True)

        assert _port_block(data["nodes"][group.input_node.node_id], "sub_in")["field_data"] is None


class TestOldSaves:
    def test_a_relay_with_something_upstream_takes_its_value_from_upstream_on_load(
        self, graph_with_library_system
    ):
        """Guards Q23's accepted break: only an orphaned relay keeps a stale saved value."""
        graph = graph_with_library_system
        listener = make_node(graph, LISTEN, position=(0, 0))
        emitter = make_node(graph, EMIT, position=(600, 0))
        edge = make_edge(graph, listener.node_id, "listen_callback", emitter.node_id, "edge_callback")
        reroute_id = _split_with_reroute(graph, edge.edge_id)
        data = graph.to_dict()
        for port_id in ("in", "out"):
            _port_block(data["nodes"][reroute_id], port_id)["field_data"] = {"value": "stale"}

        graph.clear()
        graph.load_from_dict(data)

        reloaded_emitter = graph.node_wrappers[emitter.node_id]
        reloaded_listener = graph.node_wrappers[listener.node_id]
        assert subscriptions(reloaded_emitter) == [reloaded_listener.node.value("listen_callback")]
