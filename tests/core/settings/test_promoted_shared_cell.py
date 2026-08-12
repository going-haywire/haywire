"""Promoted setting reads through the SHARED cell.

A promoted port borrows the setting's DataField cell by reference, so the
setting and the port return the same value because they share the cell.
"""

import pytest


def _link_and_push(node, pid, value):
    """Drive an upstream value onto a promoted inlet: stamp a linked edge so
    ``is_linked()`` is True, then push the value through the port's field."""
    port = node.ports[pid]
    port._linked_edges["fake_edge"] = object()  # is_linked() only checks length
    port.set_value(value, edge_id="fake_edge")


@pytest.mark.integration
def test_promoted_inlet_and_setting_share_one_cell(make_node_with_setting):
    node = make_node_with_setting(accessor="filter", field="threshold")
    from haywire.core.node.promotion import promote_setting

    promote_setting(node, "filter", "threshold")
    desc = type(node.filter).__dict__["threshold"]
    pid = desc.storage_key

    # Identity: one cell, two views.
    assert node.ports[pid]._data is node.filter._cell_for(desc)


@pytest.mark.integration
def test_driven_promoted_inlet_read_via_shared_cell(make_node_with_setting):
    node = make_node_with_setting(accessor="filter", field="threshold")
    from haywire.core.node.promotion import promote_setting

    promote_setting(node, "filter", "threshold")
    pid = type(node.filter).__dict__["threshold"].storage_key

    _link_and_push(node, pid, 0.9)
    # The setting reflects the driven value — same cell, no bridge.
    assert node.filter.threshold == 0.9
    assert node.ports[pid].get_value() == 0.9


@pytest.mark.integration
def test_disconnected_promoted_inlet_falls_back_to_setting(make_node_with_setting):
    node = make_node_with_setting(accessor="filter", field="threshold")
    from haywire.core.node.promotion import promote_setting

    promote_setting(node, "filter", "threshold")
    # Not linked / not driven → the shared cell holds the setting default.
    assert node.filter.threshold == 0.5


@pytest.mark.integration
def test_unpromoted_read_does_not_touch_ports(make_node_with_setting):  # noqa: D401
    """The unpromoted read path must never consult ``node.ports`` — there is no
    per-read promotion lookup on the hot path (the setting is oblivious to ports;
    an edge-driven promoted inlet marks _set_keys at write time instead)."""
    node = make_node_with_setting(accessor="filter", field="threshold")

    class _RaiseOnGet(dict):
        def get(self, *a, **k):  # type: ignore[override]
            raise AssertionError("unpromoted read must not consult node.ports")

    node.ports = _RaiseOnGet()
    assert node.filter.threshold == 0.5  # resolves without consulting ports


@pytest.mark.integration
def test_promoted_config_and_setting_share_one_cell(make_node_with_setting):
    node = make_node_with_setting(accessor="filter", field="threshold")
    from haywire.core.node.promotion import promote_setting
    from haywire.core.types.enums import PortType

    promote_setting(node, "filter", "threshold", PortType.CONFIG)
    desc = type(node.filter).__dict__["threshold"]
    pid = desc.storage_key

    # Identity: one cell, two views.
    assert node.ports[pid]._data is node.filter._cell_for(desc)


@pytest.mark.integration
def test_promoted_config_has_no_edge_and_reads_setting_value(make_node_with_setting):
    """A CONFIG port is pinless — there is no edge to drive it. Writing the
    setting directly (its only write path) is reflected on the shared cell."""
    node = make_node_with_setting(accessor="filter", field="threshold")
    from haywire.core.node.promotion import promote_setting
    from haywire.core.types.enums import PortType

    promote_setting(node, "filter", "threshold", PortType.CONFIG)
    pid = type(node.filter).__dict__["threshold"].storage_key

    node.filter.threshold = 0.9
    assert node.ports[pid].get_value() == 0.9
