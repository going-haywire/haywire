"""Settings.promote()/demote() — bag-level convenience API over the module-level
promote_setting/demote_setting functions in haywire.core.node.promotion.

General-purpose across all three directions (INLET/OUTLET/CONFIG); intended
primarily for a node's post_init() call sites, e.g.:

    def post_init(self):
        self.my_bag.promote("my_choice_field", PortType.CONFIG)
"""

import pytest

from haywire.core.types.enums import PortType

pytestmark = pytest.mark.integration


def test_bag_promote_creates_inlet(make_node_with_setting):
    node = make_node_with_setting(accessor="filter", field="threshold")
    node.filter._promote("threshold", PortType.INLET)
    pid = type(node.filter).__dict__["threshold"].storage_key
    assert pid in node.ports
    assert node.ports[pid].is_inlet()


def test_bag_promote_creates_outlet(make_node_with_setting):
    node = make_node_with_setting(accessor="filter", field="threshold")
    node.filter._promote("threshold", PortType.OUTLET)
    pid = type(node.filter).__dict__["threshold"].storage_key
    assert pid in node.ports
    assert node.ports[pid].is_outlet()


def test_bag_promote_creates_config(make_node_with_setting):
    node = make_node_with_setting(accessor="filter", field="threshold")
    node.filter._promote("threshold", PortType.CONFIG)
    pid = type(node.filter).__dict__["threshold"].storage_key
    assert pid in node.ports
    assert node.ports[pid].is_config()


def test_bag_demote_removes_port(make_node_with_setting):
    node = make_node_with_setting(accessor="filter", field="threshold")
    node.filter._promote("threshold", PortType.CONFIG)
    pid = type(node.filter).__dict__["threshold"].storage_key
    node.filter._demote("threshold")
    assert pid not in node.ports
    assert node.filter._is_promoted("threshold") is False


def test_bag_promote_default_direction_is_inlet(make_node_with_setting):
    """Matches promote_setting's own default (PortType.INLET)."""
    node = make_node_with_setting(accessor="filter", field="threshold")
    node.filter._promote("threshold")
    pid = type(node.filter).__dict__["threshold"].storage_key
    assert node.ports[pid].is_inlet()


def test_bag_promote_raises_for_ineligible_direction(make_node_with_setting):
    from haywire.core.settings import Promotable

    node = make_node_with_setting(accessor="filter", field="threshold")
    type(node.filter).__dict__["threshold"]._promotable = Promotable.OUTLET
    with pytest.raises(ValueError, match="cannot be promoted"):
        node.filter._promote("threshold", PortType.INLET)


def test_removing_a_promoted_pin_through_the_action_is_undoable(make_node_with_setting):
    from unittest.mock import MagicMock

    from haywire.core.undo.actions.graph_actions import RemovePortAction

    node = make_node_with_setting(accessor="filter", field="threshold")
    node.filter._promote("threshold", PortType.OUTLET)
    pid = type(node.filter).__dict__["threshold"].storage_key
    graph = MagicMock()
    graph.get_node_wrapper.return_value.node = node

    action = RemovePortAction(graph, "n1", pid)
    action.execute()
    assert pid not in node.ports
    assert node.filter._is_promoted("threshold") is False

    action.undo()
    assert node.ports[pid].is_outlet()
    assert node.filter._is_promoted("threshold") is True


def test_promoting_through_the_action_is_undoable(make_node_with_setting):
    from unittest.mock import MagicMock

    from haywire.core.undo.actions.graph_actions import PromoteSettingAction

    node = make_node_with_setting(accessor="filter", field="threshold")
    pid = type(node.filter).__dict__["threshold"].storage_key
    graph = MagicMock()
    graph.get_node_wrapper.return_value.node = node

    action = PromoteSettingAction(graph, "n1", "filter", "threshold", PortType.INLET)
    action.execute()
    assert node.ports[pid].is_inlet()

    action.undo()
    assert pid not in node.ports
    assert node.filter._is_promoted("threshold") is False

    action.execute()
    assert node.ports[pid].is_inlet()


def test_a_promoted_port_inherits_operable():
    from haywire.barn.builtin.types import FLOAT
    from haywire.core.node.promotion import _metadata_to_port_kwargs
    from haywire.core.settings import setting

    locked = setting(1.0, label="Locked", type_=FLOAT, operable=False)
    plain = setting(1.0, label="Plain", type_=FLOAT)

    assert locked.operable is False
    assert plain.operable is True
    assert _metadata_to_port_kwargs(locked)["operable"] is False
    assert "operable" not in _metadata_to_port_kwargs(plain)
