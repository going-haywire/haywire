"""Tests for ``PanelRegistry.get_redraw_signals_for_focus``.

The framework's actual panel-driven signal-bus wiring lives in the host
editor (today: ``PropertiesEditor``) and is tested end-to-end in
``tests/ui/properties_editor/test_event_bus_migration.py``. This file
covers only the registry-level helper that produces the signal-type
union — the building block both the host editor and any future panel
introspection / tooling use.
"""

from __future__ import annotations

from dataclasses import dataclass

import haywire.core.graph.editor  # noqa: F401 — circular-import guard

from haywire.core.library.identity import LibraryIdentity
from haywire.core.session.signals import Signal
from haywire.ui.panel import BasePanel, panel
from haywire.ui.panel.focus import Focus
from haywire.ui.panel.registry import PanelRegistry


_FAKE_LIBRARY_IDENTITY = LibraryIdentity(
    label="fake",
    version="0.1",
    description="test",
    url="",
    help_url="",
    author="",
    author_url="",
    folder_path="/tmp/fake",
    module_name="fake",
    id="fake",
)


# ----------------------------------------------------------------------
# Test signal types + fixtures
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class _PanelSignalX(Signal):
    pass


@dataclass(frozen=True)
class _PanelSignalY(Signal):
    pass


@dataclass(frozen=True)
class _UnrelatedSignal(Signal):
    pass


class _TestFocus(Focus):
    id = "panel_redraw_union_test_focus"
    label = "T"
    icon = "x"

    @classmethod
    def available(cls, ctx):
        return True


class _OtherFocus(Focus):
    id = "panel_redraw_union_other_focus"
    label = "O"
    icon = "o"

    @classmethod
    def available(cls, ctx):
        return True


# Display panels (no actions: annotation) — get_redraw_signals_for_focus only
# considers display panels.
@panel(
    focus=_TestFocus,
    label="X",
    redraw_on=(_PanelSignalX,),
    registry_id="prtest_panel_x",
)
class _PanelX(BasePanel):
    def draw(self, ctx, layout):
        pass


@panel(
    focus=_TestFocus,
    label="Y",
    redraw_on=(_PanelSignalY,),
    registry_id="prtest_panel_y",
)
class _PanelY(BasePanel):
    def draw(self, ctx, layout):
        pass


@panel(
    focus=_TestFocus,
    label="Empty",
    registry_id="prtest_panel_empty",
)
class _PanelNoRedraw(BasePanel):
    def draw(self, ctx, layout):
        pass


@panel(
    focus=_OtherFocus,
    label="Other",
    redraw_on=(_UnrelatedSignal,),
    registry_id="prtest_panel_other_focus",
)
class _PanelOtherFocus(BasePanel):
    def draw(self, ctx, layout):
        pass


# ----------------------------------------------------------------------
# PanelRegistry.get_redraw_signals_for_focus
# ----------------------------------------------------------------------


def _fresh_registry_with_panels(*panel_classes: type) -> PanelRegistry:
    reg = PanelRegistry()
    for cls in panel_classes:
        reg._register_class(cls, library_identity=_FAKE_LIBRARY_IDENTITY)
    return reg


def test_get_redraw_signals_for_focus_unions_matching_panel_redraw_on():
    reg = _fresh_registry_with_panels(_PanelX, _PanelY, _PanelNoRedraw)
    signals = reg.get_redraw_signals_for_focus(_TestFocus)
    assert signals == {_PanelSignalX, _PanelSignalY}


def test_get_redraw_signals_for_focus_skips_panels_for_other_focus():
    reg = _fresh_registry_with_panels(_PanelX, _PanelOtherFocus)
    signals = reg.get_redraw_signals_for_focus(_TestFocus)
    # _PanelOtherFocus's redraw_on is excluded — it belongs to _OtherFocus.
    assert signals == {_PanelSignalX}


def test_get_redraw_signals_for_focus_returns_empty_when_no_panels_for_focus():
    reg = _fresh_registry_with_panels(_PanelX, _PanelY)
    signals = reg.get_redraw_signals_for_focus(_OtherFocus)
    assert signals == set()


def test_get_redraw_signals_for_focus_skips_empty_redraw_on_tuple():
    reg = _fresh_registry_with_panels(_PanelNoRedraw)
    signals = reg.get_redraw_signals_for_focus(_TestFocus)
    assert signals == set()
