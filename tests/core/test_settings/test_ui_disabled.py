"""
Tests for the ui_disabled mechanism on Settings/setting():

- ui_disabled= kwarg seeds initial disabled state
- set_ui_disabled()/set_ui_disabled_all()/is_ui_disabled() runtime API
- the dedicated UI-state channel (subscribe_ui_state/unsubscribe_ui_state):
  transition-only firing, teardown, cleanup()
- the hard invariant that UI-disabled state never touches the field's
  DataField cell (no on_changed, no is_dirty) — the value channel stays
  value-only. The panel-side wiring (enabled_when, widget disabling) is
  tested in tests/ui/panel/test_ui_disabled_row_state.py.
"""

import logging

from haywire.core.settings import Settings, setting
from haywire.barn.builtin.types import BOOL, FLOAT


class UiDisabledSettings(Settings):
    normal = setting[FLOAT](1.0, label="Normal")
    starts_disabled = setting[FLOAT](2.0, label="Starts Disabled", ui_disabled=True)
    flag = setting[BOOL](True, label="Flag")


class TestUiDisabledDefault:
    def test_field_without_ui_disabled_starts_enabled(self):
        bag = UiDisabledSettings()
        assert bag.is_ui_disabled("normal") is False

    def test_field_with_ui_disabled_true_starts_disabled(self):
        bag = UiDisabledSettings()
        assert bag.is_ui_disabled("starts_disabled") is True

    def test_ui_disabled_default_does_not_affect_value_or_writes(self):
        bag = UiDisabledSettings()
        assert bag.starts_disabled == 2.0
        bag.starts_disabled = 5.0
        assert bag.starts_disabled == 5.0


class TestSetUiDisabled:
    def test_set_ui_disabled_true_then_false(self):
        bag = UiDisabledSettings()
        assert bag.is_ui_disabled("normal") is False
        bag.set_ui_disabled("normal", True)
        assert bag.is_ui_disabled("normal") is True
        bag.set_ui_disabled("normal", False)
        assert bag.is_ui_disabled("normal") is False

    def test_set_ui_disabled_does_not_affect_value_or_writes(self):
        bag = UiDisabledSettings()
        bag.set_ui_disabled("normal", True)
        assert bag.normal == 1.0
        bag.normal = 9.0
        assert bag.normal == 9.0
        assert bag.is_ui_disabled("normal") is True  # unaffected by the value write

    def test_set_ui_disabled_on_a_default_disabled_field_can_re_enable(self):
        bag = UiDisabledSettings()
        assert bag.is_ui_disabled("starts_disabled") is True
        bag.set_ui_disabled("starts_disabled", False)
        assert bag.is_ui_disabled("starts_disabled") is False

    def test_is_ui_disabled_unknown_field_returns_false(self):
        bag = UiDisabledSettings()
        assert bag.is_ui_disabled("nonexistent") is False

    def test_set_ui_disabled_unknown_field_warns_and_ignores(self, caplog):
        bag = UiDisabledSettings()
        with caplog.at_level(logging.WARNING):
            bag.set_ui_disabled("nonexistent", True)
        assert any("nonexistent" in rec.message for rec in caplog.records)
        assert bag.is_ui_disabled("nonexistent") is False


class TestSetUiDisabledAll:
    def test_bulk_disable_covers_every_field(self):
        bag = UiDisabledSettings()
        bag.set_ui_disabled_all(True)
        assert bag.is_ui_disabled("normal") is True
        assert bag.is_ui_disabled("starts_disabled") is True
        assert bag.is_ui_disabled("flag") is True

    def test_bulk_enable_clears_seeded_defaults_too(self):
        bag = UiDisabledSettings()
        bag.set_ui_disabled_all(False)
        assert bag.is_ui_disabled("starts_disabled") is False

    def test_bulk_fires_one_transition_per_changed_field(self):
        bag = UiDisabledSettings()
        calls: list[tuple[str, bool]] = []
        bag.subscribe_ui_state(lambda name, disabled: calls.append((name, disabled)))
        bag.set_ui_disabled_all(True)
        # starts_disabled was already disabled (kwarg seed) — no event for it.
        assert sorted(calls) == [("flag", True), ("normal", True)]
        calls.clear()
        bag.set_ui_disabled_all(True)  # idempotent — fully silent second time
        assert calls == []


class TestUiStateChannel:
    def test_listener_fires_on_transition_only(self):
        bag = UiDisabledSettings()
        calls: list[tuple[str, bool]] = []
        bag.subscribe_ui_state(lambda name, disabled: calls.append((name, disabled)))
        bag.set_ui_disabled("normal", True)
        bag.set_ui_disabled("normal", True)  # idempotent — must NOT fire again
        bag.set_ui_disabled("normal", False)
        bag.set_ui_disabled("normal", False)  # idempotent — must NOT fire again
        assert calls == [("normal", True), ("normal", False)]

    def test_seeded_disable_then_redundant_set_does_not_fire(self):
        bag = UiDisabledSettings()
        calls: list[tuple[str, bool]] = []
        bag.subscribe_ui_state(lambda name, disabled: calls.append((name, disabled)))
        bag.set_ui_disabled("starts_disabled", True)  # already disabled via kwarg seed
        assert calls == []

    def test_unsubscribe_stops_delivery(self):
        bag = UiDisabledSettings()
        calls: list[tuple[str, bool]] = []

        def listener(name: str, disabled: bool) -> None:
            calls.append((name, disabled))

        bag.subscribe_ui_state(listener)
        bag.set_ui_disabled("normal", True)
        bag.unsubscribe_ui_state(listener)
        bag.set_ui_disabled("normal", False)
        assert calls == [("normal", True)]

    def test_cleanup_clears_listeners(self):
        bag = UiDisabledSettings()
        calls: list[tuple[str, bool]] = []
        bag.subscribe_ui_state(lambda name, disabled: calls.append((name, disabled)))
        bag.cleanup()
        bag.set_ui_disabled("normal", True)
        assert calls == []

    def test_raising_listener_does_not_break_others(self):
        bag = UiDisabledSettings()
        calls: list[tuple[str, bool]] = []

        def bad(_name: str, _disabled: bool) -> None:
            raise RuntimeError("boom")

        bag.subscribe_ui_state(bad)
        bag.subscribe_ui_state(lambda name, disabled: calls.append((name, disabled)))
        bag.set_ui_disabled("normal", True)
        assert calls == [("normal", True)]


class TestCellIsNeverTouched:
    """THE rev-2 invariant: UI-disabled state must not leak onto the value channel.

    Rev 1 signalled the panel via cell.set_value(cell.get_value()); that echo
    reached every cell subscriber (e.g. OakDCameraNode's live-control handlers,
    which push straight to camera hardware) and set is_dirty on cells that
    promoted ports share. These tests pin the fix.
    """

    def test_set_ui_disabled_fires_no_cell_event(self):
        bag = UiDisabledSettings()
        events: list[str] = []
        bag.subscribe(lambda name, value, old: events.append(name))
        bag.set_ui_disabled("normal", True)
        bag.set_ui_disabled("normal", False)
        assert events == []

    def test_set_ui_disabled_does_not_mark_cell_dirty(self):
        bag = UiDisabledSettings()
        descriptor = type(bag)._property_settings()["normal"]
        cell = bag._cell_for(descriptor)
        cell.is_dirty = False
        bag.set_ui_disabled("normal", True)
        assert cell.is_dirty is False
