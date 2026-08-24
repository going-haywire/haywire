"""ActivityEditor — identity, formatting, and the account-menu reveal path."""

import pytest

pytestmark = pytest.mark.unit


def test_editor_lands_in_the_info_slot_on_context():
    from haybale_studio.editors.activity_editor import ActivityEditor
    from haywire.ui.editor.identity import OpenBehavior, SlotName

    identity = ActivityEditor.class_identity
    assert identity.default_slot is SlotName.INFO
    # ON_CONTEXT: a singleton tab opened on demand and closeable — the account
    # panel reveals it with binding_id=None, which ON_PAYLOAD would reject.
    assert identity.opens is OpenBehavior.ON_CONTEXT


def test_editor_is_visible_to_every_tier():
    from haybale_studio.editors.activity_editor import ActivityEditor
    from haywire.core.access import AccessTier

    assert ActivityEditor.class_identity.access is AccessTier.VIEW


def test_account_panel_is_a_view_tier_entry_in_the_account_menu():
    """The entry point is a panel in the same library as the editor, not a
    TopBar chip in core: core naming a barn registry key is the dependency
    direction this panel exists to avoid."""
    from unittest.mock import MagicMock

    from haybale_studio.panels.account.account import OpenActivityPanel
    from haywire.barn.builtin.surfaces import AccountMenu
    from haywire.core.access import AccessTier

    assert OpenActivityPanel.class_identity.surface is AccountMenu
    assert OpenActivityPanel.class_identity.access is AccessTier.VIEW
    assert OpenActivityPanel.poll(MagicMock()) is True


def test_account_panel_button_reveals_the_activity_editor(monkeypatch):
    """Drives the real ``draw`` and fires the real ``on_click``, so a wrong
    editor class or a dropped label is caught here rather than in the browser."""
    from unittest.mock import MagicMock

    from haybale_studio.editors.activity_editor import ActivityEditor
    from haybale_studio.panels.account import account as account_mod

    clicks = []

    def fake_button(label, *, icon=None, tooltip=None, on_click=None, disabled=False):
        clicks.append(on_click)
        return MagicMock()

    monkeypatch.setattr(account_mod.hui, "button", fake_button)

    panel = account_mod.OpenActivityPanel.__new__(account_mod.OpenActivityPanel)
    panel.actions = MagicMock()
    panel.draw(MagicMock(), MagicMock())

    assert len(clicks) == 1
    clicks[0]()
    panel.actions.reveal.assert_called_once_with(ActivityEditor, None, ActivityEditor.class_identity.label)


def test_editor_redraws_on_farmhand_activity():
    from haybale_studio.editors.activity_editor import ActivityEditor
    from haywire.core.signals import FarmhandActivity

    # The @redraw_on decorator stamps `_haywire_redraw_on`; the framework reads
    # it at editor instantiation to build the subscription set.
    from haywire.core.session.handlers import _REDRAW_ON_ATTR

    declared = getattr(ActivityEditor._on_activity, _REDRAW_ON_ATTR, ())
    assert FarmhandActivity in declared


# -- formatting --------------------------------------------------------------


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [(0.0, "0ms"), (0.12, "120ms"), (0.999, "999ms"), (1.0, "1.0s"), (5.5, "5.5s"), (90.0, "1m 30s")],
)
def test_format_duration(seconds, expected):
    from haybale_studio.editors.activity_editor import format_duration

    assert format_duration(seconds) == expected


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [(0.4, "just now"), (5.0, "5s ago"), (90.0, "1m ago"), (7200.0, "2h ago")],
)
def test_format_age(seconds, expected):
    from haybale_studio.editors.activity_editor import format_age

    assert format_age(seconds) == expected


# -- _safe_loads (detail popup payload parsing) -------------------------------


def test_safe_loads_parses_valid_json():
    from haybale_studio.editors.activity_editor import _safe_loads

    assert _safe_loads('{"a": 1}') == {"a": 1}


def test_safe_loads_falls_back_to_raw_text_on_truncated_json():
    """Truncation (see activity.py) can cut mid-token — the popup must still render."""
    from haybale_studio.editors.activity_editor import _safe_loads

    truncated = '{"a": "aaaa...[truncated]'
    assert _safe_loads(truncated) == truncated


# -- clear button --------------------------------------------------------------


def test_clear_button_wipes_history_and_redraws_without_touching_running_calls():
    from unittest.mock import MagicMock

    from haybale_studio.editors.activity_editor import ActivityEditor
    from haywire.core.farmhand.activity import activity_tracker

    tracker = activity_tracker()
    tracker.clear()
    try:
        tracker.start("builder", "still_going")
        tracker.finish(tracker.start("builder", "done"))
        assert tracker.recent() != []

        editor = ActivityEditor.__new__(ActivityEditor)
        editor.wrapper = MagicMock()
        editor._clear()

        assert tracker.recent() == []
        assert tracker.current("builder") is not None  # running call untouched
        editor.wrapper.redraw.assert_called_once()
    finally:
        tracker.clear()
