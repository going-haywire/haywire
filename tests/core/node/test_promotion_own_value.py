"""A linked promoted inlet shows its edge's value; the setting keeps, saves and reveals its own value."""

import pytest

from tests.core.node.test_promotion_single_cell import _link_and_push, _make_mixed_bag_node

pytestmark = pytest.mark.integration


def _promoted_inlet(make_node_with_setting):
    from haywire.core.node.promotion import promote_setting

    node = make_node_with_setting(accessor="filter", field="threshold")
    promote_setting(node, "filter", "threshold")
    return node, type(node.filter).__dict__["threshold"].storage_key


def test_a_setting_write_while_linked_keeps_the_edge_value_in_front(make_node_with_setting):
    node, pid = _promoted_inlet(make_node_with_setting)
    _link_and_push(node, pid, 0.9)

    node.filter.threshold = 0.3

    assert node.filter.threshold == 0.9
    assert node.filter._local_value(type(node.filter).__dict__["threshold"]) == 0.3


def test_a_linked_promoted_inlet_saves_its_own_value(make_node_with_setting):
    node, pid = _promoted_inlet(make_node_with_setting)
    node.filter.threshold = 0.3
    _link_and_push(node, pid, 0.9)

    assert node.filter._to_dict()["values"] == {"threshold": 0.3}


def test_demote_reveals_the_own_value(make_node_with_setting):
    from haywire.core.node.promotion import demote_setting

    node, pid = _promoted_inlet(make_node_with_setting)
    node.filter.threshold = 0.3
    _link_and_push(node, pid, 0.9)

    demote_setting(node, pid)

    assert node.filter.threshold == 0.3


def test_a_promoted_shadow_inlet_keeps_tracking_its_global(library_system):
    from haywire.core.node.promotion import promote_setting
    from haywire.core.types.enums import PortType

    node = _make_mixed_bag_node(library_system)
    registry = library_system.get_settings_registry()
    shadowed_desc = type(node.cfg).__dict__["shadowed"]
    promote_setting(node, "cfg", "shadowed", direction=PortType.INLET)

    registry.set_global(shadowed_desc._mirror_key, 0.9)

    assert node.cfg.shadowed == 0.9
