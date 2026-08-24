"""Tests for the nesting primitive Stage 0 of ADR-0029 (Surface model) builds.

``hui.submenu_row`` / ``hui.flyout`` extend ``flyout.py``'s existing hover-open,
sibling-close, cascade-close mechanics (proven for ``flyout_category`` /
``NodeMenuBuilder``) to callers that are mutually blind and can't thread a
shared ``siblings`` list themselves — Surface-model panels, eventually, but
this module has no real panels yet, so tests simulate a panel's ``draw()``/
``draw_disabled()`` with a plain counter (``_leaves_drawn``), per the plan.

See ``docs/superpowers/plans/2026-08-23-surface-model.md``, Stage 0, and
``tests/ui/test_nested_render_mechanics.py`` for the sibling framework-proof
tests this module follows the same verification style as (introspect real
NiceGUI state — ``_render_markdown()``, ``_classes``, ``_style``,
``_is_canceled`` — never just assert a docstring's claim).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator

import pytest
from nicegui import ui
from nicegui.testing import User
from nicegui.testing.user_interaction import UserInteraction
from nicegui.testing.user_simulation import user_simulation

from haywire.ui import elements as hui
from haywire.ui.components.popup import Popup
from haywire.ui.elements.flyout import (
    FLYOUT_OPEN_DELAY_S,
    FlyoutIcon,
    SubmenuRow,
    _leaves_drawn,
    open_flyout_group,
)


@pytest.fixture
def anyio_backend() -> str:
    """Run async tests on the asyncio backend."""
    return "asyncio"


@pytest.fixture
async def user() -> AsyncGenerator[User, None]:
    """A NiceGUI ``User`` simulator without the user_plugin's main_file requirement."""
    async with user_simulation() as u:
        yield u


def _hover(user: User, element: ui.element) -> None:
    """Fire ``mouseenter`` on exactly ``element`` (no ambiguous content lookup)."""
    UserInteraction(user, {element}, None).trigger("mouseenter")


def _unhover(user: User, element: ui.element) -> None:
    """Fire ``mouseleave`` on exactly ``element``."""
    UserInteraction(user, {element}, None).trigger("mouseleave")


# ──────────────────────────────────────────────────────────────────────────────
# Both faces, standing alone
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.anyio
async def test_submenu_row_enabled_standing_alone(user: User) -> None:
    """A bare, enabled ``hui.submenu_row`` draws a row and an (empty) flyout menu."""
    captured: dict[str, object] = {}

    @ui.page("/")
    def page() -> None:
        with open_flyout_group():
            with hui.submenu_row("Export") as row:
                ui.label("leaf")
                _leaves_drawn.set(_leaves_drawn.get() + 1)
        captured["row"] = row

    await user.open("/")

    row: SubmenuRow = captured["row"]  # type: ignore[assignment]
    assert isinstance(row, SubmenuRow)
    assert row._menu is not None
    assert row._menu.value is False, "flyout should start closed"
    # Something drew -> anchor stays live, not retroactively greyed.
    assert "hw-disabled" not in row._row._classes


@pytest.mark.unit
@pytest.mark.anyio
async def test_submenu_row_disabled_standing_alone_draws_no_flyout(user: User) -> None:
    """``enabled=False`` draws only the greyed anchor row — no flyout menu at all.

    This is the reason ``SubmenuRow`` must be a class, not a ``@contextmanager``
    generator: the disabled call is never entered (bare call, no ``with``), so a
    generator body would execute nothing and draw no row at all.
    """
    captured: dict[str, object] = {}

    @ui.page("/")
    def page() -> None:
        row = hui.submenu_row("Export", enabled=False)
        captured["row"] = row

    await user.open("/")

    row: SubmenuRow = captured["row"]  # type: ignore[assignment]
    assert row._menu is None, "a disabled row must not create a flyout menu"
    assert "hw-disabled" in row._row._classes
    assert row._row._style.get("opacity") == "0.4"
    assert row._row._style.get("pointer-events") == "none"

    # It really can't be entered — the disabled draw path never tries to.
    with pytest.raises(RuntimeError):
        row.__enter__()


@pytest.mark.unit
@pytest.mark.anyio
async def test_flyout_icon_standing_alone(user: User) -> None:
    """A bare ``hui.flyout`` icon opens an (initially closed) flyout menu."""
    captured: dict[str, object] = {}

    @ui.page("/")
    def page() -> None:
        with open_flyout_group():
            with hui.flyout("image", tooltip="Image") as fly:
                ui.label("leaf")
        captured["fly"] = fly

    await user.open("/")

    fly: FlyoutIcon = captured["fly"]  # type: ignore[assignment]
    assert isinstance(fly, FlyoutIcon)
    assert fly._menu.value is False


# ──────────────────────────────────────────────────────────────────────────────
# Inside a Popup
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.anyio
async def test_submenu_row_inside_a_popup(user: User) -> None:
    """A ``SubmenuRow`` renders correctly into a ``Popup``'s content column.

    ``flyout_category`` uses ``ui.menu_item``, styled by an enclosing ``QMenu``
    that a ``Popup`` doesn't provide. ``_anchor_row`` must carry its own look —
    prove the row still renders and behaves (registers a flyout, opens on hover)
    with no ``QMenu`` ancestor at all.
    """
    captured: dict[str, object] = {}

    @ui.page("/")
    def page() -> None:
        popup = Popup(position_x=0, position_y=0)
        with popup:
            with open_flyout_group():
                with hui.submenu_row("Image", icon="image") as row:
                    ui.label("leaf")
                    _leaves_drawn.set(_leaves_drawn.get() + 1)
        captured["popup"] = popup
        captured["row"] = row

    await user.open("/")

    row: SubmenuRow = captured["row"]  # type: ignore[assignment]
    assert row._menu is not None
    assert row._row.tag == "div"  # a styled ui.row, not a ui.menu_item/QItem
    assert "hw-flyout-row" in row._row._classes


# ──────────────────────────────────────────────────────────────────────────────
# Two levels deep, two siblings per level
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.anyio
async def test_two_levels_two_siblings_opening_sibling_closes_the_other_subtree(user: User) -> None:
    """The sibling-group bug a per-panel group silently reintroduces.

    Root level has two rows (Image, Export). Each has a nested child level with
    two more rows. Opening Image's child (Filters) then opening Export at the
    root must close Image's *whole subtree*, including the still-open Filters
    flyout beneath it — proving cascade-close, not just same-level close.
    """
    captured: dict[str, object] = {}

    @ui.page("/")
    def page() -> None:
        with open_flyout_group():
            # SubmenuRow.__enter__ already pushes a fresh ambient group for its
            # own body -- a nested `open_flyout_group()` here would push a SECOND,
            # unread group and orphan Filters/Adjust from Image's `_child_flyouts`
            # (exactly the per-panel-group bug this test exists to catch).
            with hui.submenu_row("Image") as image_row:
                with hui.submenu_row("Filters") as filters_row:
                    ui.label("blur")
                    _leaves_drawn.set(_leaves_drawn.get() + 1)
                with hui.submenu_row("Adjust") as adjust_row:
                    ui.label("brightness")
                    _leaves_drawn.set(_leaves_drawn.get() + 1)
            with hui.submenu_row("Export") as export_row:
                ui.label("png")
                _leaves_drawn.set(_leaves_drawn.get() + 1)

        captured.update(
            image_row=image_row,
            filters_row=filters_row,
            adjust_row=adjust_row,
            export_row=export_row,
        )

    await user.open("/")

    image_row: SubmenuRow = captured["image_row"]  # type: ignore[assignment]
    filters_row: SubmenuRow = captured["filters_row"]  # type: ignore[assignment]
    export_row: SubmenuRow = captured["export_row"]  # type: ignore[assignment]
    assert image_row._menu is not None
    assert filters_row._menu is not None
    assert export_row._menu is not None

    # Open Image (root level) -> hover-delay elapses -> Image's flyout opens.
    _hover(user, image_row._row)
    await asyncio.sleep(FLYOUT_OPEN_DELAY_S + 0.08)
    assert image_row._menu.value is True

    # Inside Image's flyout, open Filters (child level).
    _hover(user, filters_row._row)
    await asyncio.sleep(FLYOUT_OPEN_DELAY_S + 0.08)
    assert filters_row._menu.value is True

    # Now open Export at the ROOT level — a sibling of Image, not of Filters.
    _hover(user, export_row._row)
    await asyncio.sleep(FLYOUT_OPEN_DELAY_S + 0.08)
    assert export_row._menu.value is True

    # Image's whole subtree — Image itself AND its child Filters — must have
    # closed. A per-panel/per-row sibling group would leave Filters (and
    # therefore Image) open: two live paths from the root, the bug this exists
    # to prevent.
    assert image_row._menu.value is False, "opening a root sibling must close Image"
    assert filters_row._menu.value is False, "cascade-close must reach the grandchild flyout"

    # Image's own body drew NO direct leaf -- only two nested SubmenuRows
    # (Filters, Adjust). It must NOT have greyed itself retroactively: its
    # children existing at all counts as "something drew" at Image's level.
    # This is the container-of-only-nested-rows case a reviewer flagged as
    # silently unverified -- assert on it explicitly here.
    assert "hw-disabled" not in image_row._row._classes, (
        "a row whose body is only nested SubmenuRows (no direct leaf) must stay live"
    )
    assert image_row._row._style.get("opacity") is None
    assert image_row._row._style.get("pointer-events") is None


# ──────────────────────────────────────────────────────────────────────────────
# Eager-build, lazy-DOM
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.anyio
async def test_body_is_built_eagerly_but_contributes_no_dom_while_closed(user: User) -> None:
    """The flyout body renders during construction, not on hover — but stays lazy in the DOM.

    Mirrors ``test_nested_render_mechanics.test_closed_menu_holds_children_but_renders_nothing``
    for the ``SubmenuRow``/``FlyoutIcon`` primitives specifically: the leaf label
    must exist as a real server-side child immediately (proving eager build, no
    deferred-to-hover rendering), while the closed menu's ``_render_markdown()``
    is empty (proving no client DOM leaks out before the user hovers).
    """
    captured: dict[str, object] = {}

    @ui.page("/")
    def page() -> None:
        with open_flyout_group():
            with hui.submenu_row("Image") as row:
                captured["leaf"] = ui.label("eagerly built leaf")
                _leaves_drawn.set(_leaves_drawn.get() + 1)
        captured["row"] = row

    await user.open("/")

    row: SubmenuRow = captured["row"]  # type: ignore[assignment]
    menu = row._menu
    assert menu is not None

    # Built eagerly: the leaf exists server-side without ever hovering.
    assert captured["leaf"] in menu.default_slot.children
    # Lazy in the DOM: closed contributes nothing to the client.
    assert menu.value is False
    assert menu._render_markdown() == ""

    # Opening reveals the same children -- nothing is (re)built on hover.
    menu.open()
    assert menu._render_markdown() != ""
    assert captured["leaf"] in menu.default_slot.children


@pytest.mark.unit
@pytest.mark.anyio
async def test_render_path_survives_nesting_through_submenu_row(user: User) -> None:
    """An outer ContextVar-based render-path guard survives ``SubmenuRow`` nesting.

    Some callers thread their own ``ContextVar`` render-path guard around
    whatever they draw (see ``test_nested_render_mechanics.py``). ``SubmenuRow``
    pushes and pops its own ``ContextVar``s (``_flyout_siblings``,
    ``_leaves_drawn``); it must not disturb an unrelated outer ContextVar's
    value, and that value must still be visible to code running inside the
    flyout body.
    """
    from contextvars import ContextVar

    _render_path: ContextVar[tuple[str, ...]] = ContextVar("_render_path", default=())
    seen: dict[str, tuple[str, ...]] = {}

    @ui.page("/")
    def page() -> None:
        token = _render_path.set(("root",))
        try:
            with open_flyout_group():
                with hui.submenu_row("Image"):
                    seen["inside"] = _render_path.get()
                    _leaves_drawn.set(_leaves_drawn.get() + 1)
            seen["after"] = _render_path.get()
        finally:
            _render_path.reset(token)

    await user.open("/")

    assert seen["inside"] == ("root",), "outer render-path must be visible inside the flyout body"
    assert seen["after"] == ("root",), "SubmenuRow must not corrupt the outer ContextVar on exit"


# ──────────────────────────────────────────────────────────────────────────────
# Retroactive greying — the two-case distinction
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.anyio
async def test_empty_body_greys_the_anchor_retroactively(user: User) -> None:
    """Case 1: nothing drawn at all inside the body -> anchor greys itself after exit."""
    captured: dict[str, object] = {}

    @ui.page("/")
    def page() -> None:
        with open_flyout_group():
            with hui.submenu_row("Nothing Here") as row:
                pass  # no leaf drawn, counter never incremented
        captured["row"] = row

    await user.open("/")

    row: SubmenuRow = captured["row"]  # type: ignore[assignment]
    # No user could observe the row mid-construction -- greying happens only
    # after __exit__, once the body's emptiness is known.
    assert "hw-disabled" in row._row._classes
    assert row._row._style.get("opacity") == "0.4"
    assert row._row._style.get("pointer-events") == "none"


@pytest.mark.unit
@pytest.mark.anyio
async def test_body_with_only_disabled_children_does_not_grey_the_anchor(user: User) -> None:
    """Case 2: something drew, even in a disabled/greyed form -> anchor stays live.

    A "some content drew, but all of it chose the disabled form" body must NOT
    count as empty. Simulated here the way the brief specifies: a leaf that
    itself draws in a visually-disabled state still increments the shared
    counter, because it *did* draw something.
    """
    captured: dict[str, object] = {}

    @ui.page("/")
    def page() -> None:
        with open_flyout_group():
            with hui.submenu_row("Some Disabled Content") as row:
                # A leaf choosing its own disabled/greyed form -- still a draw.
                hui.submenu_row("Unavailable Item", enabled=False)
                _leaves_drawn.set(_leaves_drawn.get() + 1)
        captured["row"] = row

    await user.open("/")

    row: SubmenuRow = captured["row"]  # type: ignore[assignment]
    assert "hw-disabled" not in row._row._classes, "a row with disabled-but-present content must stay live"
    assert row._row._style.get("opacity") is None
    assert row._row._style.get("pointer-events") is None


@pytest.mark.unit
@pytest.mark.anyio
async def test_body_containing_only_a_nested_enabled_submenu_row_does_not_grey(user: User) -> None:
    """A container whose body is ONLY a nested (enabled) SubmenuRow, no leaf, stays live.

    Constructing a nested ``SubmenuRow``/``FlyoutIcon`` must itself count as
    "something drew" at the *enclosing* level -- the gap a reviewer flagged: a
    row that hosts only further rows (no direct leaf) must not grey itself even
    though nothing incremented the counter directly. A later stage's
    ``GraphContextPanel`` is exactly this shape (a hosting panel whose body is
    purely nested ``render_surface`` calls).
    """
    captured: dict[str, object] = {}

    @ui.page("/")
    def page() -> None:
        with open_flyout_group():
            with hui.submenu_row("Image") as image_row:
                with hui.submenu_row("Filters") as filters_row:
                    ui.label("blur")
                    _leaves_drawn.set(_leaves_drawn.get() + 1)
        captured["image_row"] = image_row
        captured["filters_row"] = filters_row

    await user.open("/")

    image_row: SubmenuRow = captured["image_row"]  # type: ignore[assignment]
    filters_row: SubmenuRow = captured["filters_row"]  # type: ignore[assignment]
    assert filters_row._menu is not None

    # Image drew no direct leaf -- only the nested Filters row -- yet must stay live.
    assert "hw-disabled" not in image_row._row._classes
    assert image_row._row._style.get("opacity") is None
    assert image_row._row._style.get("pointer-events") is None


@pytest.mark.unit
@pytest.mark.anyio
async def test_body_containing_only_a_disabled_nested_submenu_row_does_not_grey(user: User) -> None:
    """A container whose ONLY child is a disabled (enabled=False) nested row stays live.

    Per the spec: a disabled nested row still renders a real greyed row -- it
    is not absent -- so it still counts as "something drew" at the parent
    level. The parent must stay live even though its only content is both
    (a) not a leaf and (b) itself in the disabled/greyed visual state.
    """
    captured: dict[str, object] = {}

    @ui.page("/")
    def page() -> None:
        with open_flyout_group():
            with hui.submenu_row("Image") as image_row:
                child = hui.submenu_row("Unavailable Filter", enabled=False)
        captured["image_row"] = image_row
        captured["child"] = child

    await user.open("/")

    image_row: SubmenuRow = captured["image_row"]  # type: ignore[assignment]
    child: SubmenuRow = captured["child"]  # type: ignore[assignment]

    # The child itself is correctly greyed (it's a disabled row, expected).
    assert "hw-disabled" in child._row._classes
    # But the PARENT must stay live -- the disabled child's existence is still
    # "something drew" at Image's level.
    assert "hw-disabled" not in image_row._row._classes, (
        "a parent whose only content is a disabled nested row must stay live"
    )
    assert image_row._row._style.get("opacity") is None
    assert image_row._row._style.get("pointer-events") is None


@pytest.mark.unit
@pytest.mark.anyio
async def test_flyout_icon_with_an_empty_body_greys_the_anchor_retroactively(user: User) -> None:
    """``FlyoutIcon``'s own case 1, mirroring ``SubmenuRow``'s: an empty body
    greys the icon anchor after exit -- ``FlyoutIcon`` shares the same
    ``__enter__``/``__exit__`` mechanism as ``SubmenuRow``, just with a
    ``ui.button`` anchor (``self._anchor``) instead of a styled row."""
    captured: dict[str, object] = {}

    @ui.page("/")
    def page() -> None:
        with open_flyout_group():
            with hui.flyout("more_horiz", tooltip="More") as icon:
                pass  # no leaf drawn, counter never incremented
        captured["icon"] = icon

    await user.open("/")

    icon: FlyoutIcon = captured["icon"]  # type: ignore[assignment]
    assert "hw-disabled" in icon._anchor._classes
    assert icon._anchor._style.get("opacity") == "0.4"
    assert icon._anchor._style.get("pointer-events") == "none"


@pytest.mark.unit
@pytest.mark.anyio
async def test_a_flyout_over_an_empty_body_at_the_popup_level_does_not_count_as_a_leaf(
    user: User,
) -> None:
    """A ``SubmenuRow``/``FlyoutIcon`` constructed directly in the POPUP's own
    top-level scope (``open_flyout_group()``, never nested inside another
    row's body) must NOT count toward the popup-emptiness leaf counter, even
    though the very same construction correctly DOES count toward an
    *enclosing row's* counter (the two tests directly above this one).

    This is the distinction ``_in_flyout_body`` exists for: a
    ``SubmenuRow``/``FlyoutIcon`` sitting in a host's top-level scope is
    architecturally a container, exactly the category ``render_panel``
    already excludes from the popup-emptiness count for hosting panels
    (``class_identity.hosts != ()`` at host_rendering.py). Without the
    distinction, a popup whose only content is one hosting panel drawing one
    currently-empty ``hui.flyout(...)`` would incorrectly read as non-empty
    and open around a single greyed, useless control -- exactly the shape of
    the real ``GraphMorePanel``/``GraphMoreActions`` before any panel is
    registered on that extension surface.

    ``counting_leaves()`` lives in ``haywire.ui.panel.host_rendering`` (the
    host-side reader of this same ``_leaves_drawn`` counter) -- imported
    locally here since this file otherwise has no reason to depend on the
    panel package.
    """
    from haywire.ui.panel.host_rendering import counting_leaves

    captured: dict[str, object] = {}

    @ui.page("/")
    def page() -> None:
        with counting_leaves() as leaves:
            with open_flyout_group():
                with hui.flyout("more_horiz", tooltip="More"):
                    pass  # nothing registered on the target surface: body is empty
            captured["leaves"] = leaves()

    await user.open("/")

    assert captured["leaves"] == 0, (
        "a FlyoutIcon sitting directly in the popup's own scope must not "
        "count as a leaf -- it is a container, like a hosting panel"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Open delay
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.anyio
async def test_hover_does_not_open_synchronously_then_opens_after_the_delay(user: User) -> None:
    """The ~120ms open delay exists: hover does not open immediately."""
    captured: dict[str, object] = {}

    @ui.page("/")
    def page() -> None:
        with open_flyout_group():
            with hui.submenu_row("Image") as row:
                ui.label("leaf")
                _leaves_drawn.set(_leaves_drawn.get() + 1)
        captured["row"] = row

    await user.open("/")

    row: SubmenuRow = captured["row"]  # type: ignore[assignment]
    assert row._menu is not None

    _hover(user, row._row)
    # Immediately after hover: must NOT be open yet.
    assert row._menu.value is False, "hover must not open the flyout synchronously"

    await asyncio.sleep(FLYOUT_OPEN_DELAY_S + 0.08)
    assert row._menu.value is True, "flyout should have opened once the delay elapsed"


@pytest.mark.unit
@pytest.mark.anyio
async def test_leaving_before_the_delay_elapses_cancels_the_pending_open(user: User) -> None:
    """A fast diagonal mouse path (hover, then leave before the delay) never opens.

    This is the debounce the delay exists for: crossing a sibling briefly on the
    way to another item must not flip it open. Cancelling on ``mouseleave`` must
    not resurrect 2.x-style close-timer machinery -- it only prevents an open
    that hasn't happened yet; closing an already-open flyout is still purely
    sibling-close / ``auto-close``.
    """
    captured: dict[str, object] = {}

    @ui.page("/")
    def page() -> None:
        with open_flyout_group():
            with hui.submenu_row("Image") as row:
                ui.label("leaf")
                _leaves_drawn.set(_leaves_drawn.get() + 1)
        captured["row"] = row

    await user.open("/")

    row: SubmenuRow = captured["row"]  # type: ignore[assignment]
    assert row._menu is not None

    _hover(user, row._row)
    _unhover(user, row._row)  # leave well before the delay elapses

    await asyncio.sleep(FLYOUT_OPEN_DELAY_S + 0.08)
    assert row._menu.value is False, "leaving before the delay elapsed must cancel the pending open"


@pytest.mark.unit
@pytest.mark.anyio
async def test_open_delay_pending_timer_is_torn_down_with_its_anchor(user: User) -> None:
    """The pending-open timer is parented to the anchor, not left dangling.

    Re-derives ``test_popup_discard_lifecycle``'s proof that ``delete()`` cancels
    a timer created inside the deleted subtree, for the pending-open timer
    specifically -- this is the guard against
    ``.insights/feedback_nicegui_async.md``'s "a ui.timer can outlive the slot it
    was created in" trap, since this timer is created from inside an event
    handler rather than during a normal draw.
    """
    captured: dict[str, object] = {}

    @ui.page("/")
    def page() -> None:
        with open_flyout_group():
            with hui.submenu_row("Image") as row:
                ui.label("leaf")
                _leaves_drawn.set(_leaves_drawn.get() + 1)
        captured["row"] = row

    await user.open("/")

    row: SubmenuRow = captured["row"]  # type: ignore[assignment]
    _hover(user, row._row)

    # Find the pending timer as a child of the anchor row (it is re-parented
    # there specifically so deleting the anchor tears the timer down with it).
    timers = [c for c in row._row.default_slot.children if isinstance(c, ui.timer)]
    assert len(timers) == 1, "expected exactly one pending open-timer parented to the anchor"
    timer = timers[0]
    assert timer._is_canceled is False

    row._row.delete()
    assert timer._is_canceled is True, "pending open-timer outlived the anchor it was created for"
