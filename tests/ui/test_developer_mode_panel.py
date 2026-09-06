"""DeveloperModePanel — the account-menu toggle for ``ctx.developer_mode``.

Drives the real ``draw()`` against a real SessionContext, so the icon/state
pairing and the write are caught here rather than in the browser.
"""

from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from nicegui import Client, ui
from nicegui.page import page as page_deco

from haywire.barn.builtin.surfaces import AccountMenu
from haywire.core.access import AccessTier
from haywire.core.session.context import SessionContext
from haywire.core.state import LibraryStateContainer, LibraryStateRegistry
from haywire.ui import elements as hui

pytestmark = pytest.mark.unit


@page_deco("/_developer_mode_panel_test")
def _noop_page() -> None:  # registration target for a headless Client
    pass


def _make_ctx() -> SessionContext:
    app = MagicMock()
    app.library_state_container = LibraryStateContainer(LibraryStateRegistry())
    ctx = SessionContext(session_id="dev-mode-test", app=cast(Any, app))
    ctx.session = MagicMock()  # signal_field writes deref self.session
    return ctx


def _panel():
    from haybale_studio.panels.account.account import DeveloperModePanel

    return DeveloperModePanel.__new__(DeveloperModePanel)


def _draw(ctx: SessionContext) -> ui.column:
    """Render the panel's row and return the anchor holding it."""
    client = Client(cast(Any, _noop_page), request=None)
    with client:
        anchor = ui.column()
        with anchor:
            _panel().draw(ctx, anchor)
    return anchor


def _walk(element):
    yield element
    for child in element.default_slot.children:
        yield from _walk(child)


def _icon_names(anchor) -> list[str]:
    return [e._props.get("name", "") for e in _walk(anchor) if isinstance(e, ui.icon)]


def _click_the_row(anchor) -> None:
    """Fire the drawn row's registered click handler headlessly."""
    clickable = [
        e
        for e in _walk(anchor)
        if any(li.type == "click" for li in getattr(e, "_event_listeners", {}).values())
    ]
    assert clickable, "the row drew no click handler"
    element = clickable[0]
    listener_id = next(iter(element._event_listeners))
    element._handle_event({"listener_id": listener_id, "args": {}})


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def test_panel_sits_on_the_account_menu():
    from haybale_studio.panels.account.account import DeveloperModePanel

    assert DeveloperModePanel.class_identity.surface is AccountMenu


def test_panel_is_view_access():
    """The flag decides whether an affordance is DRAWN, never whether it may be
    used — the editors it reveals enforce their own access — so gating the
    toggle higher would hide a read-only view and buy no safety."""
    from haybale_studio.panels.account.account import DeveloperModePanel

    assert DeveloperModePanel.class_identity.access is AccessTier.VIEW


def test_panel_always_polls_true():
    from haybale_studio.panels.account.account import DeveloperModePanel

    assert DeveloperModePanel.poll(MagicMock()) is True


# ---------------------------------------------------------------------------
# State <-> icon
# ---------------------------------------------------------------------------


def test_developer_mode_defaults_off():
    assert _make_ctx().developer_mode is False


def test_row_shows_unchecked_icon_when_off():
    anchor = _draw(_make_ctx())
    assert hui.icon.unchecked in _icon_names(anchor)
    assert hui.icon.checked not in _icon_names(anchor)


def test_row_shows_checked_icon_when_on():
    ctx = _make_ctx()
    ctx.developer_mode = True
    anchor = _draw(ctx)
    assert hui.icon.checked in _icon_names(anchor)
    assert hui.icon.unchecked not in _icon_names(anchor)


def test_the_two_state_icons_differ():
    """A pair that collapsed to one string would render an unreadable toggle
    while every other assertion here still passed."""
    assert hui.icon.checked != hui.icon.unchecked


# ---------------------------------------------------------------------------
# The write
# ---------------------------------------------------------------------------


def test_click_turns_developer_mode_on():
    ctx = _make_ctx()
    _click_the_row(_draw(ctx))

    assert ctx.developer_mode is True


def test_click_turns_developer_mode_off_again():
    """The handler must write the NEGATION of the state it drew, not a
    constant True — otherwise the row is a one-way latch."""
    ctx = _make_ctx()
    ctx.developer_mode = True
    _click_the_row(_draw(ctx))

    assert ctx.developer_mode is False


# ---------------------------------------------------------------------------
# In-place icon update
#
# The row does not close the menu, so the icon under the pointer is the only
# feedback a click gives. The menu being rebuilt on every open fixes the NEXT
# open, not the row already on screen — these assert the drawn element itself
# moves, which is what "I have to reopen the menu to see the change" was.
# ---------------------------------------------------------------------------


def test_clicking_swaps_the_icon_in_place_without_redraw():
    ctx = _make_ctx()
    anchor = _draw(ctx)
    assert _icon_names(anchor) == [hui.icon.unchecked]

    _click_the_row(anchor)

    assert _icon_names(anchor) == [hui.icon.checked], (
        "the drawn icon must update in place — reopening the menu is not the fix"
    )


def test_clicking_twice_returns_the_icon_to_unchecked():
    ctx = _make_ctx()
    anchor = _draw(ctx)

    _click_the_row(anchor)
    _click_the_row(anchor)

    assert _icon_names(anchor) == [hui.icon.unchecked]
    assert ctx.developer_mode is False


def test_the_icon_follows_the_context_not_a_captured_snapshot():
    """The second click must read ctx, not the value draw() captured — a
    handler closing over the draw-time bool flips between two constants and
    desyncs from the flag it is meant to show."""
    ctx = _make_ctx()
    anchor = _draw(ctx)

    _click_the_row(anchor)
    assert ctx.developer_mode is True
    assert _icon_names(anchor) == [hui.icon.checked]

    _click_the_row(anchor)
    assert ctx.developer_mode is False
    assert _icon_names(anchor) == [hui.icon.unchecked]
