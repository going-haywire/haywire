# tests/core/node/test_promotion_serialization.py
"""
Settings-owned promotion serialization:

- a promoted port is ABSENT from the serialized ports block
- promotion is recorded in the owning bag's "promoted" section instead
- round-trip regenerates the live port from _promoted_keys via promote_setting
- an edge into a promoted inlet survives round-trip (port exists before edges wire)
- demote clears both the port AND the settings-side _promoted_keys record

Uses "haybale-testing:node:SettingsNode" (registered test node, bag accessor "example",
field "example_float") via the graph_with_library_system/library_system fixtures,
same pattern as the sibling promotion test files in this directory.
"""

import pytest

from haywire.core.node.promotion import demote_setting, is_field_promoted, promote_setting
from haywire.core.types.enums import PortType

pytestmark = pytest.mark.integration


class TestPromotedPortNotSerialized:
    def test_promoted_port_absent_from_ports_block(self, graph_with_library_system, library_system):
        graph = graph_with_library_system
        node = graph.create_node_wrapper("haybale-testing:node:SettingsNode", position=(0, 0)).node
        promote_setting(node, "example", "example_float", PortType.INLET)
        d = node._to_dict()
        pid = type(node.example).__dict__["example_float"].storage_key
        assert pid not in d["ports"], "a promoted port must not serialize in the ports block"

    def test_promotion_recorded_in_settings_block(self, graph_with_library_system, library_system):
        graph = graph_with_library_system
        node = graph.create_node_wrapper("haybale-testing:node:SettingsNode", position=(0, 0)).node
        promote_setting(node, "example", "example_float", PortType.OUTLET)
        d = node._to_dict()
        pid = type(node.example).__dict__["example_float"].storage_key
        assert d["settings"]["example"]["promoted"] == {pid: "outlet"}


class TestRoundTripRegeneratesPort:
    def test_reload_regenerates_the_promoted_port(self, graph_with_library_system, library_system):
        graph = graph_with_library_system
        node = graph.create_node_wrapper("haybale-testing:node:SettingsNode", position=(0, 0)).node
        promote_setting(node, "example", "example_float", PortType.INLET)
        pid = type(node.example).__dict__["example_float"].storage_key

        data = node._to_dict()
        reloaded = graph.create_node_wrapper("haybale-testing:node:SettingsNode", position=(50, 0)).node
        reloaded._initialize_from_dict(data)

        assert pid in reloaded.ports, "reload must regenerate the promoted port"
        assert reloaded.ports[pid].promoted is True
        assert reloaded.ports[pid].is_inlet() is True
        assert is_field_promoted(reloaded.example, "example_float") is True


class TestEdgeIntoPromotedInletSurvives:
    def test_edge_to_promoted_inlet_round_trips(self, graph_with_library_system, library_system):
        graph = graph_with_library_system
        src = graph.create_node_wrapper("haybale-testing:node:SettingsNode", position=(0, 0))
        sink = graph.create_node_wrapper("haybale-testing:node:SettingsNode", position=(100, 0))

        promote_setting(src.node, "example", "example_float", PortType.OUTLET)
        promote_setting(sink.node, "example", "example_float", PortType.INLET)
        pid = type(src.node.example).__dict__["example_float"].storage_key

        edge = graph.create_edge_wrapper(src.node_id, pid, sink.node_id, pid)
        assert edge is not None
        assert edge.state.is_valid()

        data = graph.to_dict()
        graph.clear()
        graph.load_from_dict(data)

        reloaded_sink = graph.node_wrappers[sink.node_id].node
        assert pid in reloaded_sink.ports
        assert any(e.edge.inlet_port_id == pid for e in graph.edge_wrappers.values()), (
            "the edge into the promoted inlet must survive round-trip"
        )


class TestDemoteClearsRecord:
    def test_demote_clears_promoted_keys(self, graph_with_library_system, library_system):
        graph = graph_with_library_system
        node = graph.create_node_wrapper("haybale-testing:node:SettingsNode", position=(0, 0)).node
        promote_setting(node, "example", "example_float", PortType.INLET)
        pid = type(node.example).__dict__["example_float"].storage_key
        demote_setting(node, pid)
        assert pid not in node.ports
        assert node.example.is_promoted("example_float") is False
        assert node.example._promoted_keys == {}
