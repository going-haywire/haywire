import pytest


@pytest.mark.integration
def test_detach_panel_identifies_promoted_port(make_node_with_setting):
    """The 'Detach from setting' panel targets a promoted port — identified by the
    port being present with promoted=True at the setting's storage_key."""
    from haywire.core.node.promotion import is_field_promoted, promote_setting

    node = make_node_with_setting(accessor="filter", field="threshold")
    promote_setting(node, "filter", "threshold")
    assert is_field_promoted(node.filter, "threshold")
    pid = type(node.filter).__dict__["threshold"].storage_key
    assert node.ports[pid].promoted is True


@pytest.mark.integration
def test_remove_port_demotes_a_promoted_pin(make_node_with_setting):
    """The row's one verb reaches demotion on a promoted pin, clearing the record."""
    from haywire.core.node.promotion import is_field_promoted, promote_setting, remove_port

    node = make_node_with_setting(accessor="filter", field="threshold")
    promote_setting(node, "filter", "threshold")
    pid = type(node.filter).__dict__["threshold"].storage_key

    assert remove_port(node, pid) is True

    assert pid not in node.ports
    assert not is_field_promoted(node.filter, "threshold")
