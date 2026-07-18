"""Settings.promote()/demote() — bag-level convenience API over the module-level
promote_setting/demote_setting functions in haywire.core.node.promotion.

General-purpose across all three directions (INLET/OUTLET/CONFIG); intended
primarily for a node's post_init() call sites, e.g.:

    def post_init(self):
        self.my_bag.promote("my_choice_field", PortType.CONFIG)
"""

# Per CLAUDE.md test trap: import editor before other haywire modules.

import pytest

from haywire.core.types.enums import PortType

pytestmark = pytest.mark.integration


def test_bag_promote_creates_inlet(make_node_with_setting):
    node = make_node_with_setting(accessor="filter", field="threshold")
    node.filter.promote("threshold", PortType.INLET)
    pid = type(node.filter).__dict__["threshold"].storage_key
    assert pid in node.ports
    assert node.ports[pid].is_inlet()


def test_bag_promote_creates_outlet(make_node_with_setting):
    node = make_node_with_setting(accessor="filter", field="threshold")
    node.filter.promote("threshold", PortType.OUTLET)
    pid = type(node.filter).__dict__["threshold"].storage_key
    assert pid in node.ports
    assert node.ports[pid].is_outlet()


def test_bag_promote_creates_config(make_node_with_setting):
    node = make_node_with_setting(accessor="filter", field="threshold")
    node.filter.promote("threshold", PortType.CONFIG)
    pid = type(node.filter).__dict__["threshold"].storage_key
    assert pid in node.ports
    assert node.ports[pid].is_config()


def test_bag_demote_removes_port(make_node_with_setting):
    node = make_node_with_setting(accessor="filter", field="threshold")
    node.filter.promote("threshold", PortType.CONFIG)
    pid = type(node.filter).__dict__["threshold"].storage_key
    node.filter.demote("threshold")
    assert pid not in node.ports
    assert node.filter.is_promoted("threshold") is False


def test_bag_promote_default_direction_is_inlet(make_node_with_setting):
    """Matches promote_setting's own default (PortType.INLET)."""
    node = make_node_with_setting(accessor="filter", field="threshold")
    node.filter.promote("threshold")
    pid = type(node.filter).__dict__["threshold"].storage_key
    assert node.ports[pid].is_inlet()


def test_bag_promote_raises_for_ineligible_direction(make_node_with_setting):
    from haywire.core.settings import Promotable

    node = make_node_with_setting(accessor="filter", field="threshold")
    type(node.filter).__dict__["threshold"]._promotable = Promotable.OUTLET
    with pytest.raises(ValueError, match="cannot be promoted"):
        node.filter.promote("threshold", PortType.INLET)
