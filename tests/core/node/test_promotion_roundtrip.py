import haywire.core.graph.editor  # noqa: F401

import pytest

pytestmark = pytest.mark.integration


def test_promoted_inlet_survives_full_roundtrip(graph_with_library_system, library_system):
    """promote -> serialize -> fresh node from dict -> promoted port rebound to cell."""
    from haywire.core.node.promotion import promote_setting

    graph = graph_with_library_system
    node = graph.create_node_wrapper("testing:node:SettingsNode", position=(0, 0)).node
    promote_setting(node, "example", "example_float")
    desc = type(node.example).__dict__["example_float"]
    pid = desc.storage_key

    dumped = node._to_dict()
    assert pid in dumped["ports"]  # port STAYS in the ports block
    assert dumped["ports"][pid]["kwargs"]["promoted"] is True
    assert "recipe" in dumped["ports"][pid]  # now carries a recipe
    assert "field_data" not in dumped["ports"][pid]  # but no value

    fresh = graph.create_node_wrapper("testing:node:SettingsNode", position=(50, 0)).node
    fresh._initialize_from_dict(dumped)
    assert pid in fresh.ports
    assert fresh.ports[pid].promoted is True
    # Rebound by reference: port._data IS the fresh bag's cell.
    fdesc = type(fresh.example).__dict__["example_float"]
    assert fresh.ports[pid]._data is fresh.example._cell_for(fdesc)


def test_promoted_outlet_rebinds_and_is_lazy(graph_with_library_system, library_system):
    from haywire.core.node.promotion import promote_setting
    from haywire.core.types.enums import PortType

    graph = graph_with_library_system
    node = graph.create_node_wrapper("testing:node:SettingsNode", position=(0, 0)).node
    promote_setting(node, "example", "example_float", direction=PortType.OUTLET)
    pid = type(node.example).__dict__["example_float"].storage_key

    dumped = node._to_dict()
    fresh = graph.create_node_wrapper("testing:node:SettingsNode", position=(50, 0)).node
    fresh._initialize_from_dict(dumped)
    assert fresh.ports[pid].is_outlet()
    assert fresh.ports[pid].is_linked_lazy is True
