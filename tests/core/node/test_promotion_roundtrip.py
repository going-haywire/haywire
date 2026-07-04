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


def test_stale_promoted_port_loads_unbound(graph_with_library_system, library_system, caplog):
    """A promoted port whose setting no longer exists must not kill node load (Q2=A).

    Simulates a library that renamed/removed the setting: the serialized port id
    no longer matches any descriptor storage_key. The node must load, the port
    must remain (promoted, unbound), and a warning must be logged.
    """
    import logging

    from haywire.core.node.promotion import promote_setting

    graph = graph_with_library_system
    node = graph.create_node_wrapper("testing:node:SettingsNode", position=(0, 0)).node
    promote_setting(node, "example", "example_float")
    desc = type(node.example).__dict__["example_float"]
    pid = desc.storage_key

    dumped = node._to_dict()
    # Tamper: rename the port id to a storage_key that matches no setting.
    stale_id = pid + "_gone"
    port_blob = dumped["ports"].pop(pid)
    port_blob["kwargs"]["id"] = stale_id
    dumped["ports"][stale_id] = port_blob

    fresh = graph.create_node_wrapper("testing:node:SettingsNode", position=(50, 0)).node
    with caplog.at_level(logging.WARNING):
        fresh._initialize_from_dict(dumped)  # must NOT raise

    assert stale_id in fresh.ports
    assert fresh.ports[stale_id].promoted is True
    # Unbound: the port's field is NOT any bag cell (it is the recipe-created default field).
    fdesc = type(fresh.example).__dict__["example_float"]
    assert fresh.ports[stale_id]._data is not fresh.example._cell_for(fdesc)
    assert any(stale_id in rec.message for rec in caplog.records if rec.levelno >= logging.WARNING)
