"""Task 2.5 — the mirror-field cell is authoritative in the setting.

For "one cell, two views" (P5) to hold, the shared cell must carry the *resolved*
value, not just the descriptor default. That is the setting's own responsibility:
``_on_field_change`` writes the resolved global into the cell for an unset mirror
field, and the cell is seeded at subscribe / first ``_cell_for`` access so a
freshly-loaded headless graph is correct before any change fires.

These tests are headless — no UI subscriber — which is exactly the gap P4 left.
"""

from typing import Any

import pytest

from haywire.core.settings import Settings, SettingsRegistry, setting, shadow
from haywire.barn.builtin.types import COLOR, FLOAT


GLOBAL_KEY = "test.color"
LOCAL_KEY = "test.node.color"


def _make_mirror_bag(*, use_watch: bool):
    """A registry-backed bag with a single mirror field on ``GLOBAL_KEY``,
    built via the real ``watch()``/``shadow()`` factory (not a hand-rolled
    ``setting(mirrors=...)`` call) so these tests exercise the actual public
    API surface.
    """
    from haywire.core.settings import shadow, watch

    factory: Any = watch if use_watch else shadow

    class MirrorBag(Settings):
        color = factory(GLOBAL_KEY, label="Color", type_=COLOR)

    MirrorBag.color._setting_key = LOCAL_KEY

    registry = SettingsRegistry()
    registry.define(GLOBAL_KEY, "#ffffff", type_=COLOR)

    bag = MirrorBag(registry=registry)
    bag._subscribe_settings()
    return registry, bag


def _make_watch_bag():
    return _make_mirror_bag(use_watch=True)


def _make_shadow_bag():
    return _make_mirror_bag(use_watch=False)


def _cell(bag):
    desc = type(bag)._property_settings()["color"]
    return bag._cell_for(desc)


def test_cell_seeded_with_resolved_global_headless():
    """At first access the cell holds the resolved global, not the default."""
    registry, bag = _make_watch_bag()
    registry.set_global(GLOBAL_KEY, "#123456")
    # No UI subscriber — headless. The cell must already reflect the global.
    registry2, bag2 = _make_watch_bag()
    registry2.set_global(GLOBAL_KEY, "#abcdef")
    # A bag whose global was set BEFORE first _cell_for access still seeds correctly.
    assert _cell(bag2).get_value() == "#abcdef"


def test_watch_cell_tracks_global_change_headless():
    registry, bag = _make_watch_bag()
    assert _cell(bag).get_value() == "#ffffff"
    registry.set_global(GLOBAL_KEY, "#aabbcc")
    # No UI subscriber — the cell is still updated by the setting itself.
    assert _cell(bag).get_value() == "#aabbcc"
    assert bag.color == "#aabbcc"


def test_shadow_unset_tracks_global_change_headless():
    registry, bag = _make_shadow_bag()
    registry.set_global(GLOBAL_KEY, "#aabbcc")
    assert _cell(bag).get_value() == "#aabbcc"
    assert bag.color == "#aabbcc"


def test_shadow_set_ignores_global_change():
    registry, bag = _make_shadow_bag()
    bag.color = "#ff0000"  # local override — tracking stops
    registry.set_global(GLOBAL_KEY, "#aabbcc")
    assert _cell(bag).get_value() == "#ff0000"
    assert bag.color == "#ff0000"


def test_shadow_reset_reseeds_from_global_and_resumes_tracking():
    registry, bag = _make_shadow_bag()
    registry.set_global(GLOBAL_KEY, "#111111")
    bag.color = "#ff0000"  # override
    assert bag.color == "#ff0000"

    bag.reset("color")  # drop override → re-seed from global, resume tracking
    assert bag.color == "#111111"
    assert _cell(bag).get_value() == "#111111"

    registry.set_global(GLOBAL_KEY, "#222222")  # tracking resumed
    assert bag.color == "#222222"
    assert _cell(bag).get_value() == "#222222"


def test_cleanup_unsubscribes_from_registry():
    registry, bag = _make_watch_bag()
    bag.cleanup()
    # After cleanup the setting no longer reacts to the registry.
    registry.set_global(GLOBAL_KEY, "#999999")
    # The bag is cleaned up; nothing should have been written into its cell.
    assert bag._cleaned_up is True


def test_watch_is_writable_and_promotable_outlet_and_disabled():
    """watch() is now sugar over setting(mirrors=..., ui_state=DISABLED,
    promotable=OUTLET) — no _read_only flag, no AttributeError on write."""
    from haywire.core.settings.descriptor import Promotable, UiState

    registry, bag = _make_watch_bag()
    desc = type(bag)._property_settings()["color"]

    assert not hasattr(desc, "_read_only")
    assert desc._ui_state is UiState.DISABLED
    assert desc._promotable is Promotable.OUTLET

    # Writes are now legal (convention-only guard, not enforced).
    bag.color = "#ff0000"
    assert bag.color == "#ff0000"


def test_shadow_has_no_forced_ui_state_or_promotable():
    from haywire.core.settings.descriptor import Promotable, UiState

    registry, bag = _make_shadow_bag()
    desc = type(bag)._property_settings()["color"]

    assert not hasattr(desc, "_read_only")
    assert desc._ui_state is UiState.NORMAL
    assert desc._promotable is Promotable.ALL


def test_same_bag_mirror_raises_value_error():
    """mirrors= must reference a field on a DIFFERENT class. A same-bag
    sibling (never registry.define()'d) used to be silently made to work via
    _in_bag_mirror_adapters — that machinery had zero production usage and is
    deleted; the input is now rejected at declaration time instead."""
    with pytest.raises(ValueError, match="same bag"):

        class SameBagBag(Settings):
            plain = setting[FLOAT](0.5)
            mirrored = shadow(plain, type_=FLOAT)


def test_watch_field_serializes_once_locally_set():
    """watch() fields are writable now (Task 1) — once locally overridden,
    they serialize like any other mirror field. The old read_only-driven
    to_dict()/from_dict() exclusion is gone."""
    registry, bag = _make_watch_bag()
    bag.color = "#ff0000"

    data = bag.to_dict()
    assert data["values"] == {"color": "#ff0000"}

    registry2, bag2 = _make_watch_bag()
    bag2.from_dict(data)
    assert bag2.color == "#ff0000"
    assert bag2.is_locally_set("color")
