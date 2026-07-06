"""
Tests for the UiState mechanism on Settings/setting() (ADR 0020):

- ui_state= kwarg seeds initial state (sparse: NORMAL entries are not stored)
- set_ui_state()/set_ui_state_all()/ui_state() runtime API, incl. the
  category= bulk filter
- the dedicated UI-state channel (subscribe_ui_state/unsubscribe_ui_state):
  transition-only firing, teardown, cleanup()
- the hard invariant that UiState never touches the field's DataField cell
  (no on_changed, no is_dirty) — the value channel stays value-only. The
  panel-side wiring (enabled_when/visible_when, widget disabling, row
  hiding) is tested in tests/ui/panel/test_ui_state_row_state.py.
"""

import logging

from haywire.core.settings import Settings, UiState, setting
from haywire.barn.builtin.types import BOOL, FLOAT


class UiStateSettings(Settings):
    normal = setting[FLOAT](1.0, label="Normal")
    starts_disabled = setting[FLOAT](2.0, label="Starts Disabled", ui_state=UiState.DISABLED)
    starts_hidden = setting[FLOAT](3.0, label="Starts Hidden", ui_state=UiState.HIDDEN)
    flag = setting[BOOL](True, label="Flag")
    adv_a = setting[FLOAT](1.0, label="Adv A", category="advanced")
    adv_b = setting[FLOAT](2.0, label="Adv B", category="advanced")


class TestSeed:
    def test_field_without_ui_state_starts_normal(self):
        bag = UiStateSettings()
        assert bag.ui_state("normal") is UiState.NORMAL

    def test_seeded_disabled_and_hidden(self):
        bag = UiStateSettings()
        assert bag.ui_state("starts_disabled") is UiState.DISABLED
        assert bag.ui_state("starts_hidden") is UiState.HIDDEN

    def test_storage_is_sparse(self):
        bag = UiStateSettings()
        # Only the two non-NORMAL seeds occupy the dict.
        assert len(bag._ui_state) == 2

    def test_seed_does_not_affect_value_or_writes(self):
        bag = UiStateSettings()
        assert bag.starts_hidden == 3.0
        bag.starts_hidden = 5.0
        assert bag.starts_hidden == 5.0


class TestSetUiState:
    def test_set_and_reset_roundtrip(self):
        bag = UiStateSettings()
        bag.set_ui_state("normal", UiState.HIDDEN)
        assert bag.ui_state("normal") is UiState.HIDDEN
        bag.set_ui_state("normal", UiState.DISABLED)
        assert bag.ui_state("normal") is UiState.DISABLED
        bag.set_ui_state("normal", UiState.NORMAL)
        assert bag.ui_state("normal") is UiState.NORMAL
        assert "normal" not in bag._ui_state  # NORMAL entries are dropped, not stored

    def test_set_ui_state_does_not_affect_value_or_writes(self):
        bag = UiStateSettings()
        bag.set_ui_state("normal", UiState.HIDDEN)
        assert bag.normal == 1.0
        bag.normal = 9.0
        assert bag.normal == 9.0
        assert bag.ui_state("normal") is UiState.HIDDEN  # unaffected by the value write

    def test_seeded_field_can_be_reset_to_normal(self):
        bag = UiStateSettings()
        bag.set_ui_state("starts_disabled", UiState.NORMAL)
        assert bag.ui_state("starts_disabled") is UiState.NORMAL

    def test_ui_state_unknown_field_returns_normal(self):
        bag = UiStateSettings()
        assert bag.ui_state("nonexistent") is UiState.NORMAL

    def test_set_ui_state_unknown_field_warns_and_ignores(self, caplog):
        bag = UiStateSettings()
        with caplog.at_level(logging.WARNING):
            bag.set_ui_state("nonexistent", UiState.HIDDEN)
        assert any("nonexistent" in rec.message for rec in caplog.records)
        assert bag.ui_state("nonexistent") is UiState.NORMAL


class TestSetUiStateAll:
    def test_bulk_covers_every_field(self):
        bag = UiStateSettings()
        bag.set_ui_state_all(UiState.DISABLED)
        for name in ("normal", "starts_disabled", "starts_hidden", "flag", "adv_a", "adv_b"):
            assert bag.ui_state(name) is UiState.DISABLED

    def test_bulk_normal_clears_seeded_states_too(self):
        bag = UiStateSettings()
        bag.set_ui_state_all(UiState.NORMAL)
        assert bag.ui_state("starts_disabled") is UiState.NORMAL
        assert bag.ui_state("starts_hidden") is UiState.NORMAL

    def test_bulk_category_filter_touches_only_that_category(self):
        bag = UiStateSettings()
        bag.set_ui_state_all(UiState.HIDDEN, category="advanced")
        assert bag.ui_state("adv_a") is UiState.HIDDEN
        assert bag.ui_state("adv_b") is UiState.HIDDEN
        assert bag.ui_state("normal") is UiState.NORMAL  # root category untouched

    def test_bulk_unknown_category_warns_and_ignores(self, caplog):
        bag = UiStateSettings()
        with caplog.at_level(logging.WARNING):
            bag.set_ui_state_all(UiState.HIDDEN, category="no_such_category")
        assert any("no_such_category" in rec.message for rec in caplog.records)
        assert len(bag._ui_state) == 2  # only the seeds

    def test_bulk_fires_one_transition_per_changed_field(self):
        bag = UiStateSettings()
        calls: list[tuple[str, UiState]] = []
        bag.subscribe_ui_state(lambda name, state: calls.append((name, state)))
        bag.set_ui_state_all(UiState.DISABLED)
        # starts_disabled was already DISABLED (seed) — no event for it.
        assert sorted(calls) == [
            ("adv_a", UiState.DISABLED),
            ("adv_b", UiState.DISABLED),
            ("flag", UiState.DISABLED),
            ("normal", UiState.DISABLED),
            ("starts_hidden", UiState.DISABLED),
        ]
        calls.clear()
        bag.set_ui_state_all(UiState.DISABLED)  # idempotent — fully silent second time
        assert calls == []


class TestUiStateChannel:
    def test_listener_fires_on_transition_only(self):
        bag = UiStateSettings()
        calls: list[tuple[str, UiState]] = []
        bag.subscribe_ui_state(lambda name, state: calls.append((name, state)))
        bag.set_ui_state("normal", UiState.HIDDEN)
        bag.set_ui_state("normal", UiState.HIDDEN)  # idempotent — must NOT fire again
        bag.set_ui_state("normal", UiState.NORMAL)
        bag.set_ui_state("normal", UiState.NORMAL)  # idempotent — must NOT fire again
        assert calls == [("normal", UiState.HIDDEN), ("normal", UiState.NORMAL)]

    def test_disabled_to_hidden_is_a_transition(self):
        bag = UiStateSettings()
        calls: list[tuple[str, UiState]] = []
        bag.subscribe_ui_state(lambda name, state: calls.append((name, state)))
        bag.set_ui_state("starts_disabled", UiState.HIDDEN)
        assert calls == [("starts_disabled", UiState.HIDDEN)]

    def test_redundant_set_on_seeded_state_does_not_fire(self):
        bag = UiStateSettings()
        calls: list[tuple[str, UiState]] = []
        bag.subscribe_ui_state(lambda name, state: calls.append((name, state)))
        bag.set_ui_state("starts_disabled", UiState.DISABLED)  # already DISABLED via seed
        assert calls == []

    def test_unsubscribe_stops_delivery(self):
        bag = UiStateSettings()
        calls: list[tuple[str, UiState]] = []

        def listener(name: str, state: UiState) -> None:
            calls.append((name, state))

        bag.subscribe_ui_state(listener)
        bag.set_ui_state("normal", UiState.DISABLED)
        bag.unsubscribe_ui_state(listener)
        bag.set_ui_state("normal", UiState.NORMAL)
        assert calls == [("normal", UiState.DISABLED)]

    def test_cleanup_clears_listeners(self):
        bag = UiStateSettings()
        calls: list[tuple[str, UiState]] = []
        bag.subscribe_ui_state(lambda name, state: calls.append((name, state)))
        bag.cleanup()
        bag.set_ui_state("normal", UiState.DISABLED)
        assert calls == []

    def test_raising_listener_does_not_break_others(self):
        bag = UiStateSettings()
        calls: list[tuple[str, UiState]] = []

        def bad(_name: str, _state: UiState) -> None:
            raise RuntimeError("boom")

        bag.subscribe_ui_state(bad)
        bag.subscribe_ui_state(lambda name, state: calls.append((name, state)))
        bag.set_ui_state("normal", UiState.DISABLED)
        assert calls == [("normal", UiState.DISABLED)]


class TestCellIsNeverTouched:
    """THE rev-2 invariant, carried over unchanged: UiState must not leak onto
    the value channel. Rev 1 signalled the panel via cell.set_value(...); that
    echo reached every cell subscriber (e.g. OakDCameraNode's live-control
    handlers, which push straight to camera hardware) and set is_dirty on
    cells that promoted ports share. These tests pin the fix."""

    def test_set_ui_state_fires_no_cell_event(self):
        bag = UiStateSettings()
        events: list[str] = []
        bag.subscribe(lambda name, value, old: events.append(name))
        bag.set_ui_state("normal", UiState.HIDDEN)
        bag.set_ui_state("normal", UiState.NORMAL)
        assert events == []

    def test_set_ui_state_does_not_mark_cell_dirty(self):
        bag = UiStateSettings()
        descriptor = type(bag)._property_settings()["normal"]
        cell = bag._cell_for(descriptor)
        cell.is_dirty = False
        bag.set_ui_state("normal", UiState.HIDDEN)
        assert cell.is_dirty is False


class GatedSettings(Settings):
    enable_color = setting[BOOL](True, label="Enable Color")
    exposure = setting[FLOAT](20000.0, label="Exposure", metadata={"enabled_when": ("enable_color", True)})
    manual_focus = setting[FLOAT](
        0.0, label="Manual Focus", metadata={"visible_when": ("enable_color", True)}
    )
    typo_gated = setting[FLOAT](1.0, label="Typo Gated", metadata={"enabled_when": ("does_not_exist", True)})


class TestEffectiveUiState:
    def test_ungated_field_is_normal(self):
        bag = GatedSettings()
        assert bag.effective_ui_state("enable_color") is UiState.NORMAL

    def test_enabled_when_contributes_at_most_disabled(self):
        bag = GatedSettings()
        bag.enable_color = False
        assert bag.effective_ui_state("exposure") is UiState.DISABLED

    def test_visible_when_contributes_hidden(self):
        bag = GatedSettings()
        bag.enable_color = False
        assert bag.effective_ui_state("manual_focus") is UiState.HIDDEN

    def test_satisfied_gates_leave_normal(self):
        bag = GatedSettings()
        assert bag.enable_color is True  # default
        assert bag.effective_ui_state("exposure") is UiState.NORMAL
        assert bag.effective_ui_state("manual_focus") is UiState.NORMAL

    def test_severity_max_manual_hidden_beats_declarative_disabled(self):
        bag = GatedSettings()
        bag.enable_color = False  # enabled_when → DISABLED
        bag.set_ui_state("exposure", UiState.HIDDEN)  # imperative → HIDDEN
        assert bag.effective_ui_state("exposure") is UiState.HIDDEN

    def test_severity_max_declarative_hidden_beats_manual_disabled(self):
        bag = GatedSettings()
        bag.enable_color = False  # visible_when → HIDDEN
        bag.set_ui_state("manual_focus", UiState.DISABLED)
        assert bag.effective_ui_state("manual_focus") is UiState.HIDDEN

    def test_manual_state_composes_when_gates_are_satisfied(self):
        bag = GatedSettings()
        bag.set_ui_state("exposure", UiState.DISABLED)
        assert bag.effective_ui_state("exposure") is UiState.DISABLED

    def test_unknown_controller_is_skipped_silently(self):
        bag = GatedSettings()
        assert bag.effective_ui_state("typo_gated") is UiState.NORMAL

    def test_unknown_name_returns_normal(self):
        bag = GatedSettings()
        assert bag.effective_ui_state("nonexistent") is UiState.NORMAL

    def test_effective_state_never_touches_cells(self):
        bag = GatedSettings()
        events: list[str] = []
        bag.subscribe(lambda name, value, old: events.append(name))
        bag.effective_ui_state("exposure")
        bag.effective_ui_state("manual_focus")
        assert events == []
