"""Tests for ``PanelRegistry.get_redraw_signals``.

The framework's actual panel-driven signal-bus wiring lives in the host
editor (today: ``PropertiesEditor``) and is tested end-to-end in
``tests/ui/properties_editor/test_event_bus_migration.py``. This file
covers only the registry-level helper that produces the signal-type
union — the building block both the host editor and any future panel
introspection / tooling use.
"""

from __future__ import annotations

from dataclasses import dataclass


from haywire.core.library.identity import LibraryIdentity
from haywire.core.signals import Signal
from haywire.ui.panel import BasePanel, panel
from haywire.ui.surface import Surface
from haywire.ui.panel.registry import PanelRegistry


_FAKE_LIBRARY_IDENTITY = LibraryIdentity(
    label="fake",
    version="0.1",
    folder_path="/tmp/fake",
    module_name="fake",
    name="fake",
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


class _TestSurface(Surface):
    __test__ = False

    id = "panel_redraw_union_test_surface"


class _OtherSurface(Surface):
    id = "panel_redraw_union_other_surface"


class _NestedSurface(Surface):
    id = "panel_redraw_union_nested_surface"


class _DeepSurface(Surface):
    id = "panel_redraw_union_deep_surface"


@panel(
    surface=_TestSurface,
    label="X",
    redraw_on=(_PanelSignalX,),
    registry_id="prtest_panel_x",
)
class _PanelX(BasePanel):
    def draw(self, ctx, layout):
        pass


@panel(
    surface=_TestSurface,
    label="Y",
    redraw_on=(_PanelSignalY,),
    registry_id="prtest_panel_y",
)
class _PanelY(BasePanel):
    def draw(self, ctx, layout):
        pass


@panel(
    surface=_TestSurface,
    label="Empty",
    registry_id="prtest_panel_empty",
)
class _PanelNoRedraw(BasePanel):
    def draw(self, ctx, layout):
        pass


@panel(
    surface=_OtherSurface,
    label="Other",
    redraw_on=(_UnrelatedSignal,),
    registry_id="prtest_panel_other_surface",
)
class _PanelOtherSurface(BasePanel):
    def draw(self, ctx, layout):
        pass


# ----------------------------------------------------------------------
# PanelRegistry.get_redraw_signals
# ----------------------------------------------------------------------


def _fresh_registry_with_panels(*panel_classes: type) -> PanelRegistry:
    reg = PanelRegistry()
    for cls in panel_classes:
        reg._register_class(cls, library_identity=_FAKE_LIBRARY_IDENTITY)
    return reg


def test_get_redraw_signals_unions_matching_panel_redraw_on():
    reg = _fresh_registry_with_panels(_PanelX, _PanelY, _PanelNoRedraw)
    signals = reg.get_redraw_signals(_TestSurface)
    assert signals == {_PanelSignalX, _PanelSignalY}


def test_get_redraw_signals_skips_panels_on_another_surface():
    reg = _fresh_registry_with_panels(_PanelX, _PanelOtherSurface)
    signals = reg.get_redraw_signals(_TestSurface)
    # _PanelOtherSurface's redraw_on is excluded — it sits on _OtherSurface.
    assert signals == {_PanelSignalX}


def test_get_redraw_signals_returns_empty_when_a_surface_has_no_panels():
    reg = _fresh_registry_with_panels(_PanelX, _PanelY)
    signals = reg.get_redraw_signals(_OtherSurface)
    assert signals == set()


def test_get_redraw_signals_skips_empty_redraw_on_tuple():
    reg = _fresh_registry_with_panels(_PanelNoRedraw)
    signals = reg.get_redraw_signals(_TestSurface)
    assert signals == set()


# ----------------------------------------------------------------------
# The union spans the whole hosts= tree
# ----------------------------------------------------------------------


@panel(
    surface=_TestSurface,
    hosts=(_NestedSurface,),
    label="Hosting",
    registry_id="prtest_panel_hosting",
)
class _PanelHosting(BasePanel):
    def draw(self, ctx, layout):
        pass


@panel(
    surface=_NestedSurface,
    hosts=(_DeepSurface,),
    label="Nested",
    redraw_on=(_PanelSignalY,),
    registry_id="prtest_panel_nested",
)
class _PanelNested(BasePanel):
    def draw(self, ctx, layout):
        pass


@panel(
    surface=_DeepSurface,
    label="Deep",
    redraw_on=(_UnrelatedSignal,),
    registry_id="prtest_panel_deep",
)
class _PanelDeep(BasePanel):
    def draw(self, ctx, layout):
        pass


def test_get_redraw_signals_walks_into_hosted_surfaces():
    """A long-lived host subscribes on mount, before anything has rendered, so
    the union has to be computable from the static hosts= tree. A missing
    subscription looks exactly like a signal that never fired."""
    reg = _fresh_registry_with_panels(_PanelX, _PanelHosting, _PanelNested, _PanelDeep)
    assert reg.get_redraw_signals(_TestSurface) == {
        _PanelSignalX,
        _PanelSignalY,
        _UnrelatedSignal,
    }


def test_get_redraw_signals_picks_up_a_panel_two_levels_down():
    reg = _fresh_registry_with_panels(_PanelHosting, _PanelNested, _PanelDeep)
    assert _UnrelatedSignal in reg.get_redraw_signals(_TestSurface)


def test_get_redraw_signals_terminates_on_a_cycle():
    """A cycle is logged at registration, not rejected — the walk must still
    terminate rather than recurse forever."""
    reg = PanelRegistry()

    @panel(
        surface=_TestSurface,
        hosts=(_NestedSurface,),
        label="Down",
        registry_id="prtest_cycle_down",
    )
    class _Down(BasePanel):
        def draw(self, ctx, layout):
            pass

    @panel(
        surface=_NestedSurface,
        hosts=(_TestSurface,),
        label="Up",
        redraw_on=(_PanelSignalX,),
        registry_id="prtest_cycle_up",
    )
    class _Up(BasePanel):
        def draw(self, ctx, layout):
            pass

    reg._register_class(_Down, library_identity=_FAKE_LIBRARY_IDENTITY)
    reg._register_class(_Up, library_identity=_FAKE_LIBRARY_IDENTITY)

    # Both panels registered despite the cycle; the walk is visited-set guarded.
    assert reg.get_redraw_signals(_TestSurface) == {_PanelSignalX}


def test_registration_logs_a_warning_naming_both_edges_of_the_cycle(caplog):
    """``_report_cycles`` is the early signal; ``render_surface``'s re-entry
    guard is the enforcement (tested separately). The log fires on the
    *second* panel's registration — the one that closes the loop — and both
    panels are still in the registry afterward (this is 'logged, not
    rejected', per ``_report_cycles``'s own docstring)."""
    reg = PanelRegistry()

    @panel(
        surface=_TestSurface,
        hosts=(_NestedSurface,),
        label="Down",
        registry_id="prtest_cycle_log_down",
    )
    class _Down(BasePanel):
        def draw(self, ctx, layout):
            pass

    @panel(
        surface=_NestedSurface,
        hosts=(_TestSurface,),
        label="Up",
        registry_id="prtest_cycle_log_up",
    )
    class _Up(BasePanel):
        def draw(self, ctx, layout):
            pass

    import logging

    with caplog.at_level(logging.WARNING, logger="haywire.ui.panel.registry"):
        reg._register_class(_Down, library_identity=_FAKE_LIBRARY_IDENTITY)
        assert not caplog.records, "no cycle yet — only one panel is registered"

        reg._register_class(_Up, library_identity=_FAKE_LIBRARY_IDENTITY)

    cycle_warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(cycle_warnings) == 1
    message = cycle_warnings[0].getMessage()
    # Names BOTH edges of the cycle: the registering panel (_Up) and its
    # surface (_NestedSurface, the loop's start/end), AND the other panel
    # that closes the loop (_Down) and the surface it sits on (_TestSurface,
    # the intermediate hop) — not the starting surface repeated twice. A
    # prior version of this message bound both %r slots to the same value,
    # so an author debugging a real cross-library cycle saw one panel and
    # one surface, never the panel or surface on the other side of the loop.
    assert "prtest_cycle_log_up" in message
    assert _NestedSurface.id in message
    assert "prtest_cycle_log_down" in message
    assert _TestSurface.id in message

    # Both panels still registered — the log is a signal, not a rejection.
    assert _Down in reg.get_panels(_TestSurface)
    assert _Up in reg.get_panels(_NestedSurface)
