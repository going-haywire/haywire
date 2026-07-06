import haywire.core.graph.editor  # noqa: F401

import pytest

pytestmark = pytest.mark.integration


def test_promoted_inlet_survives_full_roundtrip(graph_with_library_system, library_system):
    """promote -> serialize -> fresh node from dict -> promoted port regenerated + rebound to cell.

    ADR 0019: the promoted port is ABSENT from the serialized ports block —
    its promotion is recorded in the settings bag instead and the port is
    regenerated on load via regenerate_promoted_ports."""
    from haywire.core.node.promotion import promote_setting

    graph = graph_with_library_system
    node = graph.create_node_wrapper("testing:node:SettingsNode", position=(0, 0)).node
    promote_setting(node, "example", "example_float")
    desc = type(node.example).__dict__["example_float"]
    pid = desc.storage_key

    dumped = node._to_dict()
    assert pid not in dumped["ports"]  # promoted port is NOT in the ports block
    assert dumped["settings"]["example"]["promoted"] == {pid: "inlet"}

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


def test_stale_promoted_key_skips_regeneration(graph_with_library_system, library_system, caplog):
    """A _promoted_keys entry whose storage_key matches no setting must not kill
    node load (Q2=A).

    ADR 0019: simulates a library that renamed/removed the setting — the
    "promoted" record in the settings block no longer matches any descriptor
    storage_key. The node must load, no port is regenerated for the stale key
    (there is nothing to bind), and a warning must be logged.
    """
    import logging

    from haywire.core.node.promotion import promote_setting

    graph = graph_with_library_system
    node = graph.create_node_wrapper("testing:node:SettingsNode", position=(0, 0)).node
    promote_setting(node, "example", "example_float")
    desc = type(node.example).__dict__["example_float"]
    pid = desc.storage_key

    dumped = node._to_dict()
    # Tamper: rename the promoted key to a storage_key that matches no setting.
    stale_id = pid + "_gone"
    promoted_block = dumped["settings"]["example"]["promoted"]
    promoted_block[stale_id] = promoted_block.pop(pid)

    fresh = graph.create_node_wrapper("testing:node:SettingsNode", position=(50, 0)).node
    with caplog.at_level(logging.WARNING):
        fresh._initialize_from_dict(dumped)  # must NOT raise

    assert stale_id not in fresh.ports  # nothing to regenerate a port from
    assert any(stale_id in rec.message for rec in caplog.records if rec.levelno >= logging.WARNING)
