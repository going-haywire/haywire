import haywire.core.graph.editor  # noqa: F401

import pytest

from haywire.core.types.enums import PortType


@pytest.mark.integration
def test_promoted_port_wire_shape_is_value_less(make_node_with_setting):
    """A promoted port serializes as promoted:true + id + port_type, NO recipe,
    NO field_data — the value round-trips through the settings block only."""
    node = make_node_with_setting(accessor="filter", field="threshold")
    from haywire.core.node.promotion import encode_promoted_port_id, promote_setting

    for direction in (PortType.INLET, PortType.OUTLET):
        pid = encode_promoted_port_id("filter", "threshold")
        promote_setting(node, "filter", "threshold", direction=direction)
        entry = node._to_dict()["ports"][pid]

        assert entry["kwargs"].get("promoted") is True
        assert entry["kwargs"]["id"] == pid
        assert "recipe" not in entry
        assert "field_data" not in entry

        from haywire.core.node.promotion import demote_setting

        demote_setting(node, pid)


@pytest.mark.integration
@pytest.mark.parametrize("direction", [PortType.INLET, PortType.OUTLET])
def test_driven_promoted_port_roundtrips_binding_by_reference(make_node_with_setting, direction):
    """A driven-then-saved promoted port restores the binding by reference
    (port._data is the setting cell) AND the value, for inlet + outlet."""
    node = make_node_with_setting(accessor="filter", field="threshold")
    from haywire.core.node.promotion import encode_promoted_port_id, promote_setting

    promote_setting(node, "filter", "threshold", direction=direction)
    pid = encode_promoted_port_id("filter", "threshold")
    # Drive a value through the setting (widget-like write); shared cell holds it.
    node.filter.threshold = 0.42

    data = node._to_dict()
    restored = type(node)("n2", node.wrapper)
    restored._initialize_from_dict(data)

    assert pid in restored.ports
    desc = type(restored.filter).__dict__["threshold"]
    # Bound by reference: the restored port shares the restored setting's cell.
    assert restored.ports[pid]._data is restored.filter._cell_for(desc)
    # And the value round-tripped (via the settings block).
    assert restored.filter.threshold == 0.42


@pytest.mark.integration
def test_unset_promoted_field_persists_no_value(make_node_with_setting):
    """An UNSET promoted field: the settings entry is empty and the value resolves
    from the default on load (no persisted value)."""
    node = make_node_with_setting(accessor="filter", field="threshold")
    from haywire.core.node.promotion import promote_setting

    promote_setting(node, "filter", "threshold")
    data = node._to_dict()
    # settings.filter carries no value for the unset field.
    assert data["settings"].get("filter", {}) == {}

    restored = type(node)("n2", node.wrapper)
    restored._initialize_from_dict(data)
    assert restored.filter.threshold == 0.5  # the descriptor default
