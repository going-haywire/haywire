import pytest

pytestmark = pytest.mark.integration


def test_promoted_port_id_is_storage_key(make_node_with_setting):
    from haywire.core.node.promotion import promote_setting

    node = make_node_with_setting(accessor="filter", field="threshold")
    promote_setting(node, "filter", "threshold")
    desc = type(node.filter).__dict__["threshold"]
    assert desc.storage_key in node.ports
    assert node.ports[desc.storage_key].promoted is True


def test_promote_leaves_the_field_unset(make_node_with_setting):
    """Promotion changes where a setting shows, not its opinion: nothing is marked locally set."""
    from haywire.core.node.promotion import promote_setting

    node = make_node_with_setting(accessor="filter", field="threshold")
    desc = type(node.filter).__dict__["threshold"]
    promote_setting(node, "filter", "threshold")
    assert node.filter._is_set(desc) is False


def test_promote_binds_shared_cell(make_node_with_setting):
    from haywire.core.node.promotion import promote_setting

    node = make_node_with_setting(accessor="filter", field="threshold")
    promote_setting(node, "filter", "threshold")
    desc = type(node.filter).__dict__["threshold"]
    assert node.ports[desc.storage_key]._data is node.filter._cell_for(desc)


def test_edge_drive_reads_through_setting_without_mark_helper(make_node_with_setting):
    """An edge-driven write into the promoted inlet's shared cell is visible via
    getattr(bag, field): the setting reads the shared cell, which shows the linked value."""
    from haywire.core.node.promotion import promote_setting

    node = make_node_with_setting(accessor="filter", field="threshold")
    promote_setting(node, "filter", "threshold")
    desc = type(node.filter).__dict__["threshold"]
    port = node.ports[desc.storage_key]
    port.set_value(0.77, edge_id="some_edge")  # simulate edge drive
    assert node.filter.threshold == 0.77
