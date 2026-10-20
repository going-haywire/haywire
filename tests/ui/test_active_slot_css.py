"""The active slot lights its bars: one rule group per slot, keyed by ``<html data-hw-active-slot>``."""

from __future__ import annotations

import pytest

from haywire.ui.app.shell import ACTIVE_SLOT_CSS, STATIC_CSS
from haywire.ui.editor.identity import SlotName
from haywire.ui.themes.workbench import BaseTheme

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("slot", [s.value for s in SlotName])
def test_every_slot_lights_its_bars(slot: str) -> None:
    scope = f'html[data-hw-active-slot="{slot}"] [data-hw-slot="{slot}"]'

    assert f"{scope} .hw-slot-bar" in ACTIVE_SLOT_CSS
    assert f"{scope} .hw-slot-header" in ACTIVE_SLOT_CSS
    assert f"{scope} .hw-icon-bar-tabs .q-tab--active" in ACTIVE_SLOT_CSS


def test_the_active_colour_is_themable() -> None:
    assert "var(--hw-slot-bar-bg-active, var(--hw-bg-elevated))" in ACTIVE_SLOT_CSS
    assert "--hw-slot-bar-bg-active" in BaseTheme._CSS_TOKEN_MAP.values()


def test_it_ships_in_the_shell_css() -> None:
    assert ACTIVE_SLOT_CSS in STATIC_CSS
