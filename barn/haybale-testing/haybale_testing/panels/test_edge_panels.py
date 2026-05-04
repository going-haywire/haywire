"""Test-only edge action panels for haybale_testing.

Phase 1.5: action=TestEdgeContextActions, focus=TestEdgeFocus.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import ui

from haybale_testing.test_actions import TestEdgeContextActions
from haybale_testing.test_focuses import TestEdgeFocus
from haywire.ui import elements as hui
from haywire.ui.panel import Panel
from haywire.ui.panel.layout import PanelLayout
from haywire.ui.panel.decorator import panel

if TYPE_CHECKING:
    from haywire.core.edge.edge_wrapper import EdgeWrapperState
    from haywire.ui.context import SessionContext


def _state(ctx: "SessionContext") -> "EdgeWrapperState | None":
    wrapper = ctx.active_edge.value
    return wrapper.get_state() if wrapper is not None else None


@panel(
    action=TestEdgeContextActions,
    focus=TestEdgeFocus,
    label="Delete Connection",
    icon=hui.icon.delete,
    order=10,
)
class TestDeleteEdgePanel(Panel):
    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.active_edge.value is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: TestEdgeContextActions,
    ) -> None:
        edge = ctx.active_edge.value
        if edge is None:
            return
        edge_id = edge.edge_id
        layout.button(
            "Delete Connection",
            icon=hui.icon.delete,
            on_click=lambda: actions.test_delete_edge(edge_id),
        )


@panel(
    action=TestEdgeContextActions,
    focus=TestEdgeFocus,
    label="Inspect Connection",
    icon=hui.icon.node_info,
    order=20,
)
class TestInspectEdgePanel(Panel):
    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.active_edge.value is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: TestEdgeContextActions,
    ) -> None:
        edge = ctx.active_edge.value
        if edge is None:
            return
        edge_id = edge.edge_id
        layout.button(
            "Inspect Connection",
            icon=hui.icon.node_info,
            on_click=lambda: actions.test_inspect_edge(edge_id),
        )


@panel(
    action=TestEdgeContextActions,
    focus=TestEdgeFocus,
    label="Connection Errors",
    icon=hui.icon.error,
    order=0,
)
class TestEdgeErrorsPanel(Panel):
    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        state = _state(ctx)
        return state is not None and state.get_error() is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: TestEdgeContextActions,
    ) -> None:
        from haywire.core.errors.haywire_exception import HaywireException
        from haywire.ui.errors.error_info import error_render_detail

        state = _state(ctx)
        error = state.get_error() if state else None
        if error is None:
            return

        with layout.container:
            with ui.column().classes("w-full gap-1 p-2"):
                ui.label("⚠ Connection Error").classes("text-red-500 font-semibold text-sm")
                if isinstance(error, HaywireException):
                    ui.label(f"Category: {error.category}").classes("text-xs text-red-400 ml-1")
                    error_render_detail(error)
                else:
                    ui.label(str(error)).classes("text-red-400 text-xs whitespace-pre-wrap break-words")


@panel(
    action=TestEdgeContextActions,
    focus=TestEdgeFocus,
    label="Connection Path",
    icon=hui.icon.adapter,
    order=15,
)
class TestEdgeConnectionPathPanel(Panel):
    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        wrapper = ctx.active_edge.value
        return wrapper is not None and wrapper.edge is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: TestEdgeContextActions,
    ) -> None:
        wrapper = ctx.active_edge.value
        if wrapper is None or wrapper.edge is None:
            return
        edge = wrapper.edge

        with layout.container:
            with ui.column().classes("w-full gap-1 p-2"):
                ui.label("Connection Path").classes("font-semibold text-sm")
                ui.label(f"{edge.source_node_id} [{edge.outlet_port_id}]").classes("text-xs opacity-70")
                ui.label("↓").classes("text-xs opacity-50 ml-2")
                ui.label(f"{edge.sink_node_id} [{edge.inlet_port_id}]").classes("text-xs opacity-70")


@panel(
    action=TestEdgeContextActions,
    focus=TestEdgeFocus,
    label="Connection Warnings",
    icon=hui.icon.warning,
    order=5,
)
class TestEdgeWarningsPanel(Panel):
    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        state = _state(ctx)
        return state is not None and state.has_warning()

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: TestEdgeContextActions,
    ) -> None:
        state = _state(ctx)
        if state is None:
            return

        with layout.container:
            with ui.column().classes("w-full gap-1 p-2"):
                ui.label("⚠ Warnings").classes("text-orange-500 font-semibold text-sm")
                for warning in state.warnings:
                    ui.label(f"• {warning}").classes(
                        "text-orange-400 text-xs whitespace-pre-wrap break-words ml-1"
                    )
