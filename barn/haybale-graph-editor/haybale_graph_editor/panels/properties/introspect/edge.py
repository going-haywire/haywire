# barn/haybale-graph-editor/haybale_graph_editor/panels/properties/introspect/edge.py
"""
Edge introspect panels — PropertiesEditor display-only surface.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import ui

from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel, PanelLayout
from haywire.ui.panel.decorator import panel

from ....surfaces import EdgeInspector
from ....state.edit_state import EditState

if TYPE_CHECKING:
    from haywire.core.edge.edge_wrapper import EdgeWrapperState
    from haywire.core.session.context import SessionContext


def _state_from_context(ctx: "SessionContext") -> "EdgeWrapperState | None":
    wrapper = ctx.data[EditState].active_edge
    return wrapper.get_state() if wrapper is not None else None


def _has_edge_errors(state: "EdgeWrapperState | None") -> bool:
    return state is not None and state.get_error() is not None


def _has_edge_warnings(state: "EdgeWrapperState | None") -> bool:
    return state is not None and state.has_warning()


def _render_edge_errors(state: "EdgeWrapperState") -> None:
    from haywire.core.errors.haywire_exception import HaywireException
    from haywire.ui.errors.error_info import error_render_detail

    error = state.get_error()
    with ui.column().classes("w-full gap-1 p-2"):
        if isinstance(error, HaywireException):
            error_render_detail(error)
        else:
            hui.error_label(str(error)).classes("whitespace-pre-wrap break-words")


def _render_edge_warnings(state: "EdgeWrapperState") -> None:
    with ui.column().classes("w-full gap-1 p-2"):
        hui.warning_label("Warnings").classes("font-semibold")
        for warning in state.warnings:
            hui.warning_label(f"• {warning}").classes("whitespace-pre-wrap break-words ml-1")


@panel(
    surface=EdgeInspector,
    label="Connection Errors",
    icon=hui.icon.error,
    order=0,
)
class EdgeErrorsPanel(BasePanel):
    """Edge errors panel for PropertiesEditor."""

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return _has_edge_errors(_state_from_context(ctx))

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        state = _state_from_context(ctx)
        if state is None:
            return
        with layout.container:
            _render_edge_errors(state)


@panel(
    surface=EdgeInspector,
    label="Connection Warnings",
    icon=hui.icon.warning,
    order=5,
)
class EdgeWarningsPanel(BasePanel):
    """Edge warnings panel for PropertiesEditor."""

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return _has_edge_warnings(_state_from_context(ctx))

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        state = _state_from_context(ctx)
        if state is None:
            return
        with layout.container:
            _render_edge_warnings(state)


@panel(
    surface=EdgeInspector,
    label="Execution Statistics",
    icon=hui.icon.edge_statistics,
    default_open=False,
    order=40,
)
class EdgeStatsPanel(BasePanel):
    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.data[EditState].active_edge is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        edge_wrapper = ctx.data[EditState].active_edge
        if edge_wrapper is None:
            return
        state = edge_wrapper.get_state()
        avg_time = state.average_execution_time_us
        avg_display = f"{avg_time:.1f} μs" if avg_time > 0 else "Not measured"
        with layout:
            hui.info_row("Count", str(state.execution_count))
            hui.info_row("Avg time", avg_display)
            hui.info_row("Test value", str(state.example_test_value))
            hui.info_row("Test result", str(state.example_test_result))


@panel(
    surface=EdgeInspector,
    label="Connection Path",
    icon=hui.icon.edge_statistics,
    default_open=False,
    order=50,
)
class EdgePathPanel(BasePanel):
    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.data[EditState].active_edge is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        edge_wrapper = ctx.data[EditState].active_edge
        if edge_wrapper is None:
            return
        with layout:
            hui.info_row("From", f"{edge_wrapper.source_node_id}[{edge_wrapper.outlet_port_id}]")
            hui.info_row("To", f"{edge_wrapper.sink_node_id}[{edge_wrapper.inlet_port_id}]")
