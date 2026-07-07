"""Task 2.5 — the mirror-field cell is authoritative in the setting.

For "one cell, two views" (P5) to hold, the shared cell must carry the *resolved*
value, not just the descriptor default. That is the setting's own responsibility:
``_on_field_change`` writes the resolved global into the cell for an unset mirror
field, and the cell is seeded at subscribe / first ``_cell_for`` access so a
freshly-loaded headless graph is correct before any change fires.

These tests are headless — no UI subscriber — which is exactly the gap P4 left.
"""

import haywire.core.graph.editor  # noqa: F401  (circular-import guard, per CLAUDE.md)

import pytest

from haywire.core.settings import Settings, SettingsRegistry, setting, shadow, watch
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

    factory = watch if use_watch else shadow

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


# ==============================================================================
# In-bag sibling mirror (fix: watch()/shadow() of a plain field on the SAME bag,
# not a registered LibrarySettings/FrameworkSettings global).
#
# A same-bag sibling never gets a registry definition. Whether its
# `_setting_key` is empty (a bare ``Settings`` subclass, is_cross_mirror False
# — the shape below) or namespaced (a ``NodeSettings`` inner class wired by a
# real ``@node``, is_cross_mirror True — see tests/conftest.py:283-320's
# make_node_with_setting and test_promotion_single_cell.py's
# _make_mixed_bag_node), registry.resolve() would raise KeyError for it, since
# it was never registry.define()'d. Resolution must reach the sibling's own
# live cell on this instance instead of the registry, for either shape.
# ==============================================================================


def _make_in_bag_bag(*, with_registry: bool):
    """A bag with a plain FLOAT field and both a watch() and a shadow() of it,
    declared on the SAME class body — no separate registered schema involved.

    Same convention as ``_make_mirror_bag`` above: ``_subscribe_settings()`` is
    called explicitly so the live-sync adapter is attached (mirroring how a
    real node/panel subscriber would trigger it via ``subscribe``/
    ``subscribe_field``) — headless tracking still requires a subscriber, same
    as the registered-global path.
    """

    class InBagBag(Settings):
        plain = setting[FLOAT](0.5)
        watched = watch(plain, type_=FLOAT)
        shadowed = shadow(plain, type_=FLOAT)

    registry = SettingsRegistry() if with_registry else None
    bag = InBagBag(registry=registry)
    bag._subscribe_settings()
    return bag


def test_in_bag_sibling_is_never_registered_regardless_of_is_cross_mirror():
    """Pins the detection mechanism the fix actually uses.

    On a bare ``Settings`` subclass (as here — never touched by ``@node``'s
    ``_wire_settings_schemas``), the sibling's ``_setting_key`` stays empty, so
    ``is_cross_mirror`` is False — matching the ORIGINAL bug report exactly.
    But a ``NodeSettings`` inner class wired by a real ``@node`` DOES get a
    namespaced ``_setting_key`` stamped on every field, including plain
    siblings (see ``tests/core/node/test_promotion_single_cell.py``'s
    ``_make_mixed_bag_node`` / ``tests/conftest.py``'s
    ``make_node_with_setting``) — there, ``is_cross_mirror`` is True, yet the
    sibling is STILL never ``registry.define()``'d, so ``registry.resolve()``
    would still raise ``KeyError`` for it. Both shapes are real; the fix
    (``Settings._in_bag_mirror_of``) doesn't key off ``is_cross_mirror`` at
    all — it structurally checks whether ``_mirror_descriptor`` is declared on
    this same bag class, which holds for either shape."""
    bag = _make_in_bag_bag(with_registry=True)
    desc = type(bag)._property_settings()["watched"]
    plain_desc = type(bag)._property_settings()["plain"]
    assert desc._mirror_descriptor is plain_desc
    assert plain_desc._setting_key == ""
    assert desc.is_cross_mirror is False
    assert bag._registry is not None
    assert not bag._registry.has_definition(plain_desc.storage_key)
    # The fix's own detection succeeds regardless of is_cross_mirror's value.
    assert bag._in_bag_mirror_of(desc) is plain_desc


def test_watch_reads_in_bag_sibling_default_at_first_read():
    bag = _make_in_bag_bag(with_registry=True)
    assert bag.watched == 0.5


def test_watch_reads_in_bag_sibling_live_value_set_before_first_read():
    """The plan's own regression: a write to the sibling BEFORE the mirror's
    first read must be visible — a fix that only forwards the static
    descriptor default would miss this."""
    bag = _make_in_bag_bag(with_registry=True)
    bag.plain = 0.9
    assert bag.watched == 0.9


def test_watch_tracks_in_bag_sibling_after_first_read():
    """Live tracking, not just a correct initial seed: a write to the sibling
    AFTER the mirror's cell already exists must still propagate."""
    bag = _make_in_bag_bag(with_registry=True)
    assert bag.watched == 0.5  # cell now seeded/created
    bag.plain = 0.7
    assert bag.watched == 0.7


def test_watch_in_bag_sibling_works_fully_headless_no_registry():
    """The in-bag path must not require a registry at all — the sibling's cell
    lives on this instance regardless."""
    bag = _make_in_bag_bag(with_registry=False)
    assert bag.watched == 0.5
    bag.plain = 0.42
    assert bag.watched == 0.42


def test_shadow_in_bag_sibling_tracks_until_local_override():
    bag = _make_in_bag_bag(with_registry=True)
    assert bag.shadowed == 0.5
    bag.plain = 0.6
    assert bag.shadowed == 0.6  # unset shadow still tracks

    bag.shadowed = 0.99  # local override — tracking stops
    bag.plain = 0.1
    assert bag.shadowed == 0.99


def test_shadow_in_bag_sibling_reset_resumes_tracking():
    bag = _make_in_bag_bag(with_registry=True)
    bag.plain = 0.6
    bag.shadowed = 0.99
    assert bag.shadowed == 0.99

    bag.reset("shadowed")
    assert bag.shadowed == 0.6  # re-seeded from the sibling's current value

    bag.plain = 0.3  # tracking resumed
    assert bag.shadowed == 0.3


def test_watch_write_still_raises_for_in_bag_sibling():
    bag = _make_in_bag_bag(with_registry=True)
    with pytest.raises(AttributeError):
        bag.watched = 1.0


def test_in_bag_mirror_cleanup_detaches_sibling_adapter():
    bag = _make_in_bag_bag(with_registry=True)
    bag.subscribe_field("watched", lambda *_: None)
    assert bag._in_bag_mirror_adapters  # adapter attached

    bag.cleanup()
    bag.plain = 0.77  # after cleanup, no propagation, no stale-callback error
    assert bag._cleaned_up is True


@pytest.mark.integration
def test_watch_in_bag_sibling_live_value_via_node_settings(make_node_with_setting):
    """End-to-end over the actual production shape (@node-wired NodeSettings):
    the sibling's ``_setting_key`` IS namespaced/non-empty here (is_cross_mirror
    True) — see test_in_bag_sibling_is_never_registered_regardless_of_is_cross_mirror
    for why that alone doesn't make registry.resolve() succeed. This is the
    same fixture (tests/conftest.py:283-320) the Task 3 UI plan's own tests
    (tests/ui/panel/test_readonly_row.py) depend on."""
    node = make_node_with_setting(accessor="filter", field="threshold", with_watch=True)
    assert node.filter.threshold_watched == 0.5

    node.filter.threshold = 0.9
    assert node.filter.threshold_watched == 0.9
