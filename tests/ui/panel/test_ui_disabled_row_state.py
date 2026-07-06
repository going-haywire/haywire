# tests/ui/panel/test_ui_disabled_row_state.py
"""
Reactive panel disabling: a row rendered by _render_reactive_field_row must
reflect Settings.is_ui_disabled() (imperative — delivered over the dedicated
UI-state channel, NOT a cell event) and the enabled_when metadata convention
(declarative, same-bag, delivered over the controller field's cell channel),
both live — no full panel redraw required — and both compose via OR.

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


class EnabledWhenSettings(Settings):
    enable_color = setting[BOOL](True, label="Enable Color")
    exposure = setting[FLOAT](
        20000.0,
        label="Exposure",
        metadata={"enabled_when": ("enable_color", True)},
    )
    typo_gated = setting[FLOAT](
        1.0,
        label="Typo Gated",
        metadata={"enabled_when": ("does_not_exist", True)},
    )


def _render(bag) -> "ui.column":
    client = Client(_noop_page, request=None)
    with client:
        anchor = ui.column()
        with anchor:
            render_settings(bag)
    return anchor


class TestImperativeUiDisabled:
    def test_plain_field_row_not_disabled(self):
        bag = ImperativeSettings()
        anchor = _render(bag)
        row = _find_field_row(anchor, "plain")
        assert row is not None
        assert row._props.get("data-ui-disabled") != "true"
        assert not _widget_is_disabled(row)

    def test_ui_disabled_default_field_row_is_disabled(self):
        bag = ImperativeSettings()
        anchor = _render(bag)
        row = _find_field_row(anchor, "starts_disabled")
        assert row is not None
        assert row._props.get("data-ui-disabled") == "true"
        assert _widget_is_disabled(row)

    def test_set_ui_disabled_live_toggle_no_redraw(self):
        bag = ImperativeSettings()
        anchor = _render(bag)
        row = _find_field_row(anchor, "plain")

        bag.set_ui_state("plain", UiState.DISABLED)
        assert row._props.get("data-ui-disabled") == "true"
        assert _widget_is_disabled(row)

        bag.set_ui_state("plain", UiState.NORMAL)
        assert row._props.get("data-ui-disabled") != "true"
        assert not _widget_is_disabled(row)

    def test_live_toggle_fires_no_cell_event(self):
        """The rev-2 invariant, asserted at panel level: toggling disabled
        state while a panel is live must not echo through the value channel."""
        bag = ImperativeSettings()
        _render(bag)
        events: list[str] = []
        bag.subscribe(lambda name, value, old: events.append(name))
        bag.set_ui_state("plain", UiState.DISABLED)
        bag.set_ui_state("plain", UiState.NORMAL)
        assert events == []


class TestEnabledWhenDeclarative:
    def test_dependent_row_disabled_when_controller_condition_is_false(self):
        bag = EnabledWhenSettings()
        bag.enable_color = False
        anchor = _render(bag)
        row = _find_field_row(anchor, "exposure")
        assert row is not None
        assert row._props.get("data-ui-disabled") == "true"
        assert _widget_is_disabled(row)

    def test_dependent_row_enabled_when_controller_condition_is_true(self):
        bag = EnabledWhenSettings()
        assert bag.enable_color is True  # default
        anchor = _render(bag)
        row = _find_field_row(anchor, "exposure")
        assert row is not None
        assert row._props.get("data-ui-disabled") != "true"
        assert not _widget_is_disabled(row)

    def test_toggling_controller_live_updates_dependent_row_no_redraw(self):
        bag = EnabledWhenSettings()
        anchor = _render(bag)
        row = _find_field_row(anchor, "exposure")

        bag.enable_color = False
        assert row._props.get("data-ui-disabled") == "true"
        assert _widget_is_disabled(row)

        bag.enable_color = True
        assert row._props.get("data-ui-disabled") != "true"
        assert not _widget_is_disabled(row)

    def test_unresolvable_controller_name_fails_soft(self, caplog):
        bag = EnabledWhenSettings()
        with caplog.at_level(logging.WARNING):
            anchor = _render(bag)
        row = _find_field_row(anchor, "typo_gated")
        assert row is not None
        assert row._props.get("data-ui-disabled") != "true"
        assert not _widget_is_disabled(row)
        assert any("does_not_exist" in rec.message for rec in caplog.records)


class TestComposition:
    def test_manual_and_enabled_when_compose_via_or(self):
        bag = EnabledWhenSettings()
        assert bag.enable_color is True  # enabled_when says enabled
        bag.set_ui_state("exposure", UiState.DISABLED)  # manual override says disabled
        anchor = _render(bag)
        row = _find_field_row(anchor, "exposure")
        assert row._props.get("data-ui-disabled") == "true", "manual flag must win via OR"
