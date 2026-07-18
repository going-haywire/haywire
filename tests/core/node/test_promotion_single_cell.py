"""Characterization + single-cell tests for promotion-as-direction (P5).

Task 1 pins the *current* inlet-only promotion behaviour through the public
surface (``promote_setting``/``demote_setting``, node ``to_dict``/``from_dict``
round-trip, the read of a linked promoted inlet) so the reference-sharing rework
(Task 2+) is provably behaviour-preserving for the inlet case, and so the new
outlet direction extends a green base.

Later tasks (2, 3, 4, 5) append their own assertions here.
"""

import pytest

pytestmark = pytest.mark.integration


def _link_and_push(node, pid, value):
    """Simulate an upstream-driven value on a promoted inlet: stamp a linked edge
    so ``is_linked()`` is True, then push the value onto the port's field."""
    port = node.ports[pid]
    port._linked_edges["fake_edge"] = object()  # is_linked() only checks length
    port.set_value(value, edge_id="fake_edge")


# ---------------------------------------------------------------------------
# Task 1: characterize the current inlet promotion path
# ---------------------------------------------------------------------------


def test_promote_adds_encoded_inlet_demote_removes(make_node_with_setting):
    node = make_node_with_setting(accessor="filter", field="threshold")
    from haywire.core.node.promotion import (
        demote_setting,
        promote_setting,
    )

    pid = type(node.filter).__dict__["threshold"].storage_key
    promote_setting(node, "filter", "threshold")
    assert pid in node.ports
    assert node.ports[pid].is_inlet()

    demote_setting(node, pid)
    assert pid not in node.ports


def test_linked_promoted_inlet_observed_via_setting(make_node_with_setting):
    node = make_node_with_setting(accessor="filter", field="threshold")
    from haywire.core.node.promotion import promote_setting

    promote_setting(node, "filter", "threshold")
    pid = type(node.filter).__dict__["threshold"].storage_key

    # Unlinked → setting resolves normally (its own cell value / default).
    assert node.filter.threshold == 0.5

    # Linked + driven → getattr(bag, field) observes the driven value.
    _link_and_push(node, pid, 0.9)
    assert node.filter.threshold == 0.9


def test_watch_default_direction_rejected_shadow_default_ok(library_system):
    """watch() seeds promotable=Promotable.OUTLET (Task 2): a watch() field
    defaults to the inlet direction and is rejected (outlet-only by
    declaration, not by a separate read_only structural check); a
    ``shadow()`` field promotes to the default inlet fine. Per-direction
    coverage lives in the Task 3 tests below."""
    from haywire.core.node.promotion import promote_setting

    node = _make_mixed_bag_node(library_system)

    # watch → (default) inlet is rejected.
    with pytest.raises(ValueError):
        promote_setting(node, "cfg", "watched")

    # shadow → (default) inlet is now allowed.
    promote_setting(node, "cfg", "shadowed")
    assert type(node.cfg).__dict__["shadowed"].storage_key in node.ports


def test_promoted_inlet_roundtrips_and_rebinds(make_node_with_setting):
    node = make_node_with_setting(accessor="filter", field="threshold")
    from haywire.core.node.promotion import promote_setting

    promote_setting(node, "filter", "threshold")
    pid = type(node.filter).__dict__["threshold"].storage_key

    data = node._to_dict()
    restored = type(node)("n2", node.wrapper)
    restored._initialize_from_dict(data)

    # The promoted port survives the round-trip and the setting still reads it.
    assert pid in restored.ports
    assert restored.filter.threshold == 0.5


# ---------------------------------------------------------------------------
# Task 2: reference-sharing spine (bind_field / unbind_field)
# ---------------------------------------------------------------------------


def _descriptor_of(node, accessor, field):
    return type(getattr(node, accessor)).__dict__[field]


def test_promoted_inlet_shares_the_setting_cell_by_reference(make_node_with_setting):
    """After promote, the port's ``_data`` IS the setting's P4 cell (identity),
    and a write through the setting is observed by the port with no copy step."""
    node = make_node_with_setting(accessor="filter", field="threshold")
    from haywire.core.node.promotion import promote_setting

    promote_setting(node, "filter", "threshold")
    pid = type(node.filter).__dict__["threshold"].storage_key

    bag = node.filter
    desc = _descriptor_of(node, "filter", "threshold")
    cell = bag._cell_for(desc)

    # Identity: the port and the setting hold the *same* DataField object.
    assert node.ports[pid]._data is cell

    # A write through the descriptor is observed by the port — no copy.
    node.filter.threshold = 0.33
    assert node.ports[pid].get_value() == 0.33


def test_unbind_field_reverses_the_share(make_node_with_setting):
    """``unbind_field`` restores an independent field on the port."""
    node = make_node_with_setting(accessor="filter", field="threshold")
    from haywire.core.node.promotion import promote_setting

    promote_setting(node, "filter", "threshold")
    pid = type(node.filter).__dict__["threshold"].storage_key

    desc = _descriptor_of(node, "filter", "threshold")
    cell = node.filter._cell_for(desc)
    port = node.ports[pid]
    assert port._data is cell

    port.unbind_field()
    assert port._data is not cell


# ---------------------------------------------------------------------------
# Task 3: promote(direction) — inlet / outlet, two flag checks
# ---------------------------------------------------------------------------


def _make_mixed_bag_node(library_system):
    """A node whose bag carries a plain, a shadow, and a watch FLOAT field.

    shadowed/watched mirror TestingSettings.default_intensity (a real
    cross-bag LibrarySettings global, forced to 0.5 here) — same-bag
    mirroring is no longer supported (mirrors= must reference a field on a
    different class).
    """
    from haybale_testing.settings.testing import TestingSettings
    from haywire.barn.builtin.types import FLOAT
    from haywire.core.di.context import set_settings_registry, set_type_registry
    from haywire.core.node import BaseNode, node
    from haywire.core.settings import NodeSettings, setting, shadow, watch

    set_type_registry(library_system.get_type_registry())
    set_settings_registry(library_system.get_settings_registry())

    registry = library_system.get_settings_registry()
    registry.set_global(TestingSettings.default_intensity._setting_key, 0.5)

    bag_cls = type(
        "mixed",
        (NodeSettings,),
        {
            "plain": setting[FLOAT](0.5),
            "shadowed": shadow(TestingSettings.default_intensity, type_=FLOAT),
            "watched": watch(TestingSettings.default_intensity, type_=FLOAT),
        },
    )
    node_cls = node(label="Mixed Promotion Node")(type("_MixedPromotionNode", (BaseNode,), {"cfg": bag_cls}))
    stub = type(
        "W",
        (),
        {
            "node_id": "w1",
            "notify": lambda *a, **k: None,
            "mark_as_structuraly_dirty": lambda *a, **k: None,
            "redraw": lambda *a, **k: None,
        },
    )()
    return node_cls("n1", stub)


def test_promote_plain_to_inlet_shows_widget_when_unlinked(make_node_with_setting):
    from haywire.core.node.promotion import promote_setting
    from haywire.core.types.enums import PortType, ShowWidgetStrategy

    node = make_node_with_setting(accessor="filter", field="threshold")
    promote_setting(node, "filter", "threshold", direction=PortType.INLET)
    pid = type(node.filter).__dict__["threshold"].storage_key
    port = node.ports[pid]
    assert port.is_inlet()
    # Inlet default: NOT_LINKED → widget shows while unlinked.
    assert port.show_widget == ShowWidgetStrategy.NOT_LINKED
    assert port.should_show_widget() is True  # unlinked
    # Cell shared per direction (Task 2 invariant).
    desc = _descriptor_of(node, "filter", "threshold")
    assert port._data is node.filter._cell_for(desc)


def test_promote_plain_to_outlet_never_shows_widget_and_is_lazy(make_node_with_setting):
    from haywire.core.node.promotion import promote_setting
    from haywire.core.types.enums import PortType, ShowWidgetStrategy

    node = make_node_with_setting(accessor="filter", field="threshold")
    promote_setting(node, "filter", "threshold", direction=PortType.OUTLET)
    pid = type(node.filter).__dict__["threshold"].storage_key
    port = node.ports[pid]
    assert port.is_outlet()
    assert port.show_widget == ShowWidgetStrategy.NEVER
    # Every promoted outlet is is_linked_lazy (plain included).
    assert port.is_linked_lazy is True
    # Cell shared per direction.
    desc = _descriptor_of(node, "filter", "threshold")
    assert port._data is node.filter._cell_for(desc)


def test_default_direction_is_inlet(make_node_with_setting):
    """Back-compat: omitting direction promotes to an inlet (Plan-3 behaviour)."""
    from haywire.core.node.promotion import promote_setting

    node = make_node_with_setting(accessor="filter", field="threshold")
    promote_setting(node, "filter", "threshold")
    assert node.ports[type(node.filter).__dict__["threshold"].storage_key].is_inlet()


def test_watch_to_inlet_rejected_watch_to_outlet_ok(library_system):
    from haywire.core.node.promotion import promote_setting
    from haywire.core.types.enums import PortType

    node = _make_mixed_bag_node(library_system)
    with pytest.raises(ValueError):
        promote_setting(node, "cfg", "watched", direction=PortType.INLET)
    promote_setting(node, "cfg", "watched", direction=PortType.OUTLET)
    port = node.ports[type(node.cfg).__dict__["watched"].storage_key]
    assert port.is_outlet()
    assert port.is_linked_lazy is True


def test_shadow_to_both_directions_ok(library_system):
    from haywire.core.node.promotion import (
        demote_setting,
        promote_setting,
    )
    from haywire.core.types.enums import PortType

    node = _make_mixed_bag_node(library_system)
    shadowed_pid = type(node.cfg).__dict__["shadowed"].storage_key
    promote_setting(node, "cfg", "shadowed", direction=PortType.INLET)
    assert node.ports[shadowed_pid].is_inlet()
    demote_setting(node, shadowed_pid)

    promote_setting(node, "cfg", "shadowed", direction=PortType.OUTLET)
    port = node.ports[shadowed_pid]
    assert port.is_outlet()
    assert port.is_linked_lazy is True


def test_promoted_outlet_keeps_tracking_global_until_actually_written(library_system):
    """Promoting a shadow() field to an OUTLET must not itself mark it
    locally-set — an outlet has no write path of its own (still written
    through the normal panel/registry path, same as if it weren't promoted),
    so it must keep tracking its mirrored global exactly like an unpromoted,
    unedited shadow field. Only an INLET's edge-driven value needs the
    locally-set opinion (see _bind_port)."""
    from haywire.core.node.promotion import promote_setting
    from haywire.core.types.enums import PortType

    node = _make_mixed_bag_node(library_system)
    registry = library_system.get_settings_registry()
    shadowed_desc = type(node.cfg).__dict__["shadowed"]

    promote_setting(node, "cfg", "shadowed", direction=PortType.OUTLET)
    assert not node.cfg.is_locally_set("shadowed")

    registry.set_global(shadowed_desc._mirror_key, 0.9)
    assert node.cfg.shadowed == 0.9

    # A real local write still marks it, same as any unpromoted mirror field.
    node.cfg.shadowed = 0.3
    assert node.cfg.is_locally_set("shadowed")
    registry.set_global(shadowed_desc._mirror_key, 0.1)
    assert node.cfg.shadowed == 0.3  # tracking stopped once locally set


def test_demote_after_driven_value_keeps_the_cell_value(make_node_with_setting):
    """§C3: demote is structural — it never resets the value."""
    from haywire.core.node.promotion import (
        demote_setting,
        promote_setting,
    )
    from haywire.core.types.enums import PortType

    node = make_node_with_setting(accessor="filter", field="threshold")
    promote_setting(node, "filter", "threshold", direction=PortType.INLET)
    pid = type(node.filter).__dict__["threshold"].storage_key
    _link_and_push(node, pid, 0.77)
    assert node.filter.threshold == 0.77

    demote_setting(node, pid)
    # The cell value survives demote (recovery is an explicit reset).
    assert node.filter.threshold == 0.77
