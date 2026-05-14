"""Tests for ``PanelRegistry.get_redraw_events_for``.

The framework's actual panel-driven event-bus wiring lives in the host
editor (today: ``PropertiesEditor``) and is tested end-to-end in
``tests/ui/properties_editor/test_event_bus_migration.py``. This file
covers only the registry-level helper that produces the event-type
union — the building block both the host editor and any future panel
introspection / tooling use.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import haywire.core.graph.editor  # noqa: F401 — circular-import guard

from haywire.core.library.identity import LibraryIdentity
from haywire.core.session.events import ContextSignal
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
# Test event types + fixtures
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class _PanelEventX(ContextSignal):
    pass


@dataclass(frozen=True)
class _PanelEventY(ContextSignal):
    pass


@dataclass(frozen=True)
class _UnrelatedEvent(ContextSignal):
    pass


@runtime_checkable
class _HostActions(Protocol):
    def do_thing(self) -> None: ...


@runtime_checkable
class _OtherHostActions(Protocol):
    def do_other(self) -> None: ...


class _TestFocus(Focus):
    id = "panel_redraw_union_test_focus"
    label = "T"
    icon = "x"

    @classmethod
    def available(cls, ctx):
        return True


@panel(
    action=_HostActions,
    focus=_TestFocus,
    label="X",
    redraw_on=(_PanelEventX,),
    registry_id="prtest_panel_x",
)
class _PanelX(BasePanel):
    def draw(self, ctx, layout, actions):
        pass


@panel(
    action=_HostActions,
    focus=_TestFocus,
    label="Y",
    redraw_on=(_PanelEventY,),
    registry_id="prtest_panel_y",
)
class _PanelY(BasePanel):
    def draw(self, ctx, layout, actions):
        pass


@panel(
    action=_HostActions,
    focus=_TestFocus,
    label="Empty",
    registry_id="prtest_panel_empty",
)
class _PanelNoRedraw(BasePanel):
    def draw(self, ctx, layout, actions):
        pass


@panel(
    action=_OtherHostActions,
    focus=_TestFocus,
    label="Other",
    redraw_on=(_UnrelatedEvent,),
    registry_id="prtest_panel_other_actions",
)
class _PanelOtherActions(BasePanel):
    def draw(self, ctx, layout, actions):
        pass


# ----------------------------------------------------------------------
# PanelRegistry.get_redraw_events_for
# ----------------------------------------------------------------------


def _fresh_registry_with_panels(*panel_classes: type) -> PanelRegistry:
    reg = PanelRegistry()
    for cls in panel_classes:
        reg._register_class(cls, library_identity=_FAKE_LIBRARY_IDENTITY)
    return reg


class _HostingThing:
    def do_thing(self) -> None:
        pass


class _NonHostingThing:
    def something_else(self) -> None:
        pass


def test_get_redraw_events_for_unions_matching_panel_redraw_on():
    reg = _fresh_registry_with_panels(_PanelX, _PanelY, _PanelNoRedraw)
    events = reg.get_redraw_events_for(_HostingThing())
    assert events == {_PanelEventX, _PanelEventY}


def test_get_redraw_events_for_skips_panels_with_unsatisfied_action():
    reg = _fresh_registry_with_panels(_PanelX, _PanelOtherActions)
    events = reg.get_redraw_events_for(_HostingThing())
    # _PanelOtherActions's redraw_on is excluded — host doesn't satisfy
    # _OtherHostActions.
    assert events == {_PanelEventX}


def test_get_redraw_events_for_returns_empty_when_no_panels_apply():
    reg = _fresh_registry_with_panels(_PanelX, _PanelY)
    events = reg.get_redraw_events_for(_NonHostingThing())
    assert events == set()


def test_get_redraw_events_for_skips_empty_redraw_on_tuple():
    reg = _fresh_registry_with_panels(_PanelNoRedraw)
    events = reg.get_redraw_events_for(_HostingThing())
    assert events == set()
