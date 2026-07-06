# tests/ui/panel/test_ui_state_row_state.py
"""
Reactive panel UiState (ADR 0020): a row rendered by _render_reactive_field_row
must reflect Settings.effective_ui_state() — the imperative state (delivered
over the dedicated UI-state channel, NOT a cell event) composed with the
enabled_when / visible_when metadata conventions (declarative, same-bag,
delivered over the controller field's cell channel) via severity max — all
live, no full panel redraw required. DISABLED disables the widget and stamps
data-ui-state="disabled"; HIDDEN additionally removes the row
(set_visibility(False)).

The disabled check is mechanism-agnostic: depending on which widget class the
field resolves to, disabling lands either as Quasar :disable on a
DisableableElement root or as the §2.11 CSS on a container root / label
fallback. _widget_is_disabled() accepts either signal.
"""

import logging

import pytest

# Per CLAUDE.md test trap: import editor before other haywire modules.
import haywire.core.graph.editor  # noqa: F401

from nicegui import Client, ui

from haywire.core.settings import Settings, UiState, setting
from haywire.ui.panel.render_utils import render_settings
from haywire.barn.builtin.types import BOOL, FLOAT

pytestmark = pytest.mark.integration


def _noop_page() -> None:  # registration target for a headless Client
    pass


def _walk(element):
    """Depth-first walk over a NiceGUI element tree."""
    yield element
    for child in element.default_slot.children:
        yield from _walk(child)


def _find_field_row(root, attr_name: str):
    """Find the ``ui.row`` element carrying ``data-field="<attr_name>"``."""
    for el in _walk(root):
        props = getattr(el, "_props", {})
        if props.get("data-field") == attr_name:
            return el
    return None


def _widget_is_disabled(row) -> bool:
    """True if any element under *row* is disabled by EITHER mechanism:
    Quasar ``disable`` prop (DisableableElement root) or the §2.11 CSS
    (container root / label fallback)."""
    for el in _walk(row):
        if getattr(el, "_props", {}).get("disable") is True:
            return True
        style = getattr(el, "_style", {}) or {}
        if style.get("opacity") == "0.5" and style.get("pointer-events") == "none":
            return True
    return False


class ImperativeSettings(Settings):
    plain = setting[FLOAT](1.0, label="Plain")
    starts_disabled = setting[FLOAT](2.0, label="Starts Disabled", ui_state=UiState.DISABLED)
    starts_hidden = setting[FLOAT](3.0, label="Starts Hidden", ui_state=UiState.HIDDEN)


class GatedSettings(Settings):
    enable_color = setting[BOOL](True, label="Enable Color")
    exposure = setting[FLOAT](20000.0, label="Exposure", metadata={"enabled_when": ("enable_color", True)})
    manual_focus = setting[FLOAT](
        0.0, label="Manual Focus", metadata={"visible_when": ("enable_color", True)}
    )
    typo_gated = setting[FLOAT](1.0, label="Typo Gated", metadata={"enabled_when": ("does_not_exist", True)})


def _render(bag) -> "ui.column":
    client = Client(_noop_page, request=None)
    with client:
        anchor = ui.column()
        with anchor:
            render_settings(bag)
    return anchor


class TestImperativeUiState:
    def test_plain_field_row_is_normal(self):
        bag = ImperativeSettings()
        anchor = _render(bag)
        row = _find_field_row(anchor, "plain")
        assert row is not None
        assert row._props.get("data-ui-state") == "normal"
        assert row.visible is True
        assert not _widget_is_disabled(row)

    def test_seeded_disabled_row(self):
        bag = ImperativeSettings()
        anchor = _render(bag)
        row = _find_field_row(anchor, "starts_disabled")
        assert row is not None
        assert row._props.get("data-ui-state") == "disabled"
        assert row.visible is True
        assert _widget_is_disabled(row)

    def test_seeded_hidden_row_is_invisible(self):
        bag = ImperativeSettings()
        anchor = _render(bag)
        row = _find_field_row(anchor, "starts_hidden")
        assert row is not None  # rendered into the DOM, then visibility-toggled off
        assert row._props.get("data-ui-state") == "hidden"
        assert row.visible is False

    def test_set_ui_state_live_walk_through_all_three_states(self):
        bag = ImperativeSettings()
        anchor = _render(bag)
        row = _find_field_row(anchor, "plain")

        bag.set_ui_state("plain", UiState.DISABLED)
        assert row._props.get("data-ui-state") == "disabled"
        assert row.visible is True
        assert _widget_is_disabled(row)

        bag.set_ui_state("plain", UiState.HIDDEN)
        assert row._props.get("data-ui-state") == "hidden"
        assert row.visible is False

        bag.set_ui_state("plain", UiState.NORMAL)
        assert row._props.get("data-ui-state") == "normal"
        assert row.visible is True
        assert not _widget_is_disabled(row)

    def test_live_toggle_fires_no_cell_event(self):
        """The rev-2 invariant, asserted at panel level: toggling UiState
        while a panel is live must not echo through the value channel."""
        bag = ImperativeSettings()
        _render(bag)
        events: list[str] = []
        bag.subscribe(lambda name, value, old: events.append(name))
        bag.set_ui_state("plain", UiState.HIDDEN)
        bag.set_ui_state("plain", UiState.NORMAL)
        assert events == []


class TestDeclarativeGates:
    def test_enabled_when_false_renders_disabled(self):
        bag = GatedSettings()
        bag.enable_color = False
        anchor = _render(bag)
        row = _find_field_row(anchor, "exposure")
        assert row._props.get("data-ui-state") == "disabled"
        assert _widget_is_disabled(row)

    def test_visible_when_false_renders_hidden(self):
        bag = GatedSettings()
        bag.enable_color = False
        anchor = _render(bag)
        row = _find_field_row(anchor, "manual_focus")
        assert row._props.get("data-ui-state") == "hidden"
        assert row.visible is False

    def test_satisfied_gates_render_normal(self):
        bag = GatedSettings()
        assert bag.enable_color is True  # default
        anchor = _render(bag)
        for name in ("exposure", "manual_focus"):
            row = _find_field_row(anchor, name)
            assert row._props.get("data-ui-state") == "normal"
            assert row.visible is True
            assert not _widget_is_disabled(row)

    def test_toggling_controller_live_updates_both_rows_no_redraw(self):
        bag = GatedSettings()
        anchor = _render(bag)
        exposure = _find_field_row(anchor, "exposure")
        manual_focus = _find_field_row(anchor, "manual_focus")

        bag.enable_color = False
        assert exposure._props.get("data-ui-state") == "disabled"
        assert manual_focus.visible is False

        bag.enable_color = True
        assert exposure._props.get("data-ui-state") == "normal"
        assert manual_focus.visible is True

    def test_unresolvable_controller_name_fails_soft(self, caplog):
        bag = GatedSettings()
        with caplog.at_level(logging.WARNING):
            anchor = _render(bag)
        row = _find_field_row(anchor, "typo_gated")
        assert row is not None
        assert row._props.get("data-ui-state") == "normal"
        assert not _widget_is_disabled(row)
        assert any("does_not_exist" in rec.message for rec in caplog.records)


class TestComposition:
    def test_manual_disabled_composes_when_gates_satisfied(self):
        bag = GatedSettings()
        assert bag.enable_color is True  # gates say NORMAL
        bag.set_ui_state("exposure", UiState.DISABLED)  # imperative says DISABLED
        anchor = _render(bag)
        row = _find_field_row(anchor, "exposure")
        assert row._props.get("data-ui-state") == "disabled", "severity max: imperative must win"

    def test_declarative_hidden_beats_manual_disabled(self):
        bag = GatedSettings()
        bag.enable_color = False  # visible_when → HIDDEN
        bag.set_ui_state("manual_focus", UiState.DISABLED)
        anchor = _render(bag)
        row = _find_field_row(anchor, "manual_focus")
        assert row._props.get("data-ui-state") == "hidden"
        assert row.visible is False
