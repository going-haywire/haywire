"""
PropertiesEditor + canvas-context-menu edge panels.

Phase 1.5: dual-host panels (EdgeErrors, EdgeWarnings) split into
explicit per-host classes. DeleteEdgePanel migrates to
EdgeContextActions. ExecutionStatistics and ConnectionPath stay as
they were after Phase 1 (PropertiesEditor only).

Module-private helpers ensure both host versions render identically.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import ui

from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel, PanelLayout
from haywire.ui.panel.decorator import panel

from ..focuses import EdgeFocus
from ..state.edit_state import EditState
from ..editors.graph_canvas.handlers.context_menu_actions import EdgeContextActions

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


# ---------------------------------------------------------------------------
# EdgeErrors — dual-host (one class per host)
# ---------------------------------------------------------------------------


@panel(
    focus=EdgeFocus,
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
    actions=EdgeContextActions,
    focus=EdgeFocus,
    label="Connection Errors",
    icon=hui.icon.error,
    order=0,
)
class ContextMenuEdgeErrorsPanel(BasePanel):
    """Edge errors panel for the context menu (right-click on edge)."""

    actions: EdgeContextActions

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


# ---------------------------------------------------------------------------
# EdgeWarnings — dual-host
# ---------------------------------------------------------------------------


@panel(
    focus=EdgeFocus,
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
    actions=EdgeContextActions,
    focus=EdgeFocus,
    label="Connection Warnings",
    icon=hui.icon.warning,
    order=5,
)
class ContextMenuEdgeWarningsPanel(BasePanel):
    """Edge warnings panel for the context menu."""

    actions: EdgeContextActions

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


# ---------------------------------------------------------------------------
# DeleteEdgePanel — context-menu only
# ---------------------------------------------------------------------------


@panel(
    actions=EdgeContextActions,
    focus=EdgeFocus,
    label="Delete Connection",
    icon=hui.icon.delete,
    order=30,
)
class DeleteEdgePanel(BasePanel):
    actions: EdgeContextActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.data[EditState].active_edge is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        edge = ctx.data[EditState].active_edge
        if edge is None:
            return
        edge_id = edge.edge_id

        layout.button(
            "Delete Connection",
            icon=hui.icon.delete,
            on_click=lambda: self.actions.delete_edge(edge_id),
        )


# ---------------------------------------------------------------------------
# ExecutionStatistics + ConnectionPath — already migrated in Phase 1
# (PropertiesEditor only).
# ---------------------------------------------------------------------------


@panel(
    focus=EdgeFocus,
    label="Execution Statistics",
    icon=hui.icon.edge_statistics,
    default_open=False,
    order=40,
)
class ExecutionStatisticsEdgePanel(BasePanel):
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
        with (
            ui.card()
            .classes("w-full p-3")
            .style("background: var(--hw-bg-surface); border: 1px solid var(--hw-border);")
        ):
            hui.label(f"Execution Count: {state.execution_count}")
            avg_time = state.average_execution_time_us
            if avg_time > 0:
                hui.label(f"Average Time: {avg_time:.1f} μs")
            else:
                hui.label("Average Time: Not measured")
            hui.label(f"Tested value: {state.example_test_value}")
            hui.label(f"Tested result: {state.example_test_result}")


@panel(
    focus=EdgeFocus,
    label="Connection Path",
    icon=hui.icon.edge_statistics,
    default_open=False,
    order=50,
)
class ConnectionPathEdgePanel(BasePanel):
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
        with (
            ui.card()
            .classes("w-full p-3")
            .style("background: var(--hw-bg-surface); border: 1px solid var(--hw-border);")
        ):
            hui.label(f"{edge_wrapper.source_node_id}[{edge_wrapper.outlet_port_id}]")
            hui.label(f"{edge_wrapper.sink_node_id}[{edge_wrapper.inlet_port_id}]")
