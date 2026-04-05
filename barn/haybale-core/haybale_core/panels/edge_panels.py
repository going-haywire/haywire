"""
Context menu panels for edge actions.

Contributed to editor='context_menu', scope='edge'.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from nicegui import ui

from haywire.ui import elements as hui
from haywire.ui.panel.base import BasePanel, PanelLayout
from haywire.ui.panel.decorator import panel

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext
    from haywire.core.edge.edge_wrapper import EdgeWrapperState


def _emit(context: "SessionContext", event):
    fn = context.metadata.get("on_emit_event")
    if fn:
        fn(event)


def _state(context: "SessionContext") -> "EdgeWrapperState | None":
    wrapper = context.active_edge
    return wrapper.get_state() if wrapper is not None else None


@panel(
    editors=["context_menu", "properties"],
    scopes="edge",
    label="Connection Errors",
    icon=hui.icon.error,
    order=10,
)
class EdgeErrorsPanel(BasePanel):
    @classmethod
    def poll(cls, context: "SessionContext") -> bool:
        state = _state(context)
        return state is not None and state.get_error() is not None

    def draw(self, context: "SessionContext", layout: PanelLayout) -> None:
        from nicegui import ui
        from haywire.core.errors.haywire_exception import HaywireException
        from haywire.ui.errors.error_info import error_render_detail

        state = _state(context)
        error = state.get_error() if state else None
        if error is None:
            return

        with layout._container:
            with ui.column().classes("w-full gap-1 p-2"):
                ui.label("⚠ Connection Error").classes("hw-text-danger font-semibold text-sm")
                if isinstance(error, HaywireException):
                    ui.label(f"Category: {error.category}").classes("text-xs hw-text-danger ml-1")
                    error_render_detail(error)
                else:
                    ui.label(str(error)).classes("hw-text-danger text-xs whitespace-pre-wrap break-words")


@panel(
    editors=["context_menu", "properties"],
    scopes="edge",
    label="Connection Warnings",
    icon=hui.icon.warning,
    order=20,
)
class EdgeWarningsPanel(BasePanel):
    @classmethod
    def poll(cls, context: "SessionContext") -> bool:
        state = _state(context)
        return state is not None and state.has_warning()

    def draw(self, context: "SessionContext", layout: PanelLayout) -> None:
        from nicegui import ui

        state = _state(context)
        if state is None:
            return

        with layout._container:
            with ui.column().classes("w-full gap-1 p-2"):
                ui.label("⚠ Warnings").classes("hw-text-warning font-semibold text-sm")
                for warning in state.warnings:
                    ui.label(f"• {warning}").classes(
                        "hw-text-warning text-xs whitespace-pre-wrap break-words ml-1"
                    )


@panel(
    editors=["context_menu"],
    scopes="edge",
    label="Delete Connection",
    icon=hui.icon.delete,
    order=30,
)
class DeleteEdgePanel(BasePanel):
    @classmethod
    def poll(cls, context: "SessionContext") -> bool:
        return context.active_edge is not None

    def draw(self, context: "SessionContext", layout: PanelLayout) -> None:
        from haywire.ui.graph_canvas.event_definitions import UserRemoveEvent

        edge_id = context.active_edge.edge_id

        def _delete():
            _emit(context, UserRemoveEvent(nodes=[], edges=[edge_id]))

        layout.button("🗑 Delete Connection", on_click=_delete)


@panel(
    editors=["properties"],
    scopes="edge",
    label="Execution Statistics",
    icon=hui.icon.edge_statistics,
    default_open=False,
    order=40,
)
class ExecutionStatisticsEdgePanel(BasePanel):
    @classmethod
    def poll(cls, context: "SessionContext") -> bool:
        return context.active_edge is not None

    def draw(self, context: "SessionContext", layout: PanelLayout) -> None:
        edge_wrapper = context.active_edge
        state = edge_wrapper.get_state()
        with (
            ui.card()
            .classes("w-full p-3")
            .style("background: var(--hw-bg-surface); border: 1px solid var(--hw-border);")
        ):
            ui.label(f"Execution Count: {state.execution_count}").classes("text-xs hw-text-body")
            avg_time = state.average_execution_time_us
            if avg_time > 0:
                ui.label(f"Average Time: {avg_time:.1f} μs").classes("text-xs hw-text-body")
            else:
                ui.label("Average Time: Not measured").classes("text-xs hw-text-dim")
            ui.label(f"Tested value: {state.example_test_value}").classes("text-xs hw-text-muted ml-2")
            ui.label(f"Tested result: {state.example_test_result}").classes("text-xs hw-text-muted ml-2")


@panel(
    editors=["properties"],
    scopes="edge",
    label="Connection Path",
    icon=hui.icon.edge_statistics,
    default_open=False,
    order=50,
)
class ConnectionPathEdgePanel(BasePanel):
    @classmethod
    def poll(cls, context: "SessionContext") -> bool:
        return context.active_edge is not None

    def draw(self, context: "SessionContext", layout: PanelLayout) -> None:
        edge_wrapper = context.active_edge
        with (
            ui.card()
            .classes("w-full p-3")
            .style("background: var(--hw-bg-surface); border: 1px solid var(--hw-border);")
        ):
            ui.label(f"{edge_wrapper.source_node_id}[{edge_wrapper.outlet_port_id}]").classes(
                "text-xs hw-text-body ml-2"
            )
            ui.label(f"{edge_wrapper.sink_node_id}[{edge_wrapper.inlet_port_id}]").classes(
                "text-xs hw-text-body ml-2 mt-1"
            )
