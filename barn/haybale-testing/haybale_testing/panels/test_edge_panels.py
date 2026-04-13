"""
Test-only edge action panels for haybale_testing.

Uses editors="test_inspector", scopes="test_edge" to avoid
clashing with the production editor/scope namespace.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.ui.panel.base import BasePanel, PanelLayout
from haywire.ui.panel.decorator import panel
from haywire.ui import elements as hui

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
    editors="test_inspector",
    scopes="test_edge",
    label="Delete Connection",
    icon="delete",
    order=10,
)
class TestDeleteEdgePanel(BasePanel):
    @classmethod
    def poll(cls, context: "SessionContext") -> bool:
        return context.active_edge is not None

    def draw(self, context: "SessionContext", layout: PanelLayout) -> None:
        from haywire.ui.graph_canvas.event_definitions import UserRemoveEvent

        edge_id = context.active_edge.edge_id

        def _delete():
            _emit(context, UserRemoveEvent(nodes=[], edges=[edge_id]))

        layout.button("Delete Connection", icon=hui.icon.delete, on_click=_delete)


@panel(
    editors="test_inspector",
    scopes="test_edge",
    label="Inspect Connection",
    icon=hui.icon.node_info,
    order=20,
)
class TestInspectEdgePanel(BasePanel):
    @classmethod
    def poll(cls, context: "SessionContext") -> bool:
        return context.active_edge is not None

    def draw(self, context: "SessionContext", layout: PanelLayout) -> None:
        from haywire.ui.graph_canvas.connection_info_popup import EdgeInfoPopup

        edge_wrapper = context.active_edge
        pos = context.metadata.get("context_menu_screen_pos", (100, 100))

        def _inspect():
            popup = EdgeInfoPopup()
            popup.show(
                x=pos[0],
                y=pos[1],
                edge_id=edge_wrapper.edge_id,
                edge=edge_wrapper.edge,
                state=edge_wrapper.get_state(),
            )

        layout.button("Inspect Connection", icon=hui.icon.node_info, on_click=_inspect)


@panel(
    editors="test_inspector",
    scopes="test_edge",
    label="Connection Errors",
    icon=hui.icon.error,
    order=0,
)
class TestEdgeErrorsPanel(BasePanel):
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

        with layout.container:
            with ui.column().classes("w-full gap-1 p-2"):
                ui.label("⚠ Connection Error").classes("text-red-500 font-semibold text-sm")
                if isinstance(error, HaywireException):
                    ui.label(f"Category: {error.category}").classes("text-xs text-red-400 ml-1")
                    error_render_detail(error)
                else:
                    ui.label(str(error)).classes("text-red-400 text-xs whitespace-pre-wrap break-words")


@panel(
    editors="test_inspector",
    scopes="test_edge",
    label="Connection Path",
    icon=hui.icon.adapter,
    order=15,
)
class TestEdgeConnectionPathPanel(BasePanel):
    @classmethod
    def poll(cls, context: "SessionContext") -> bool:
        wrapper = context.active_edge
        return wrapper is not None and wrapper.edge is not None

    def draw(self, context: "SessionContext", layout: PanelLayout) -> None:
        from nicegui import ui

        edge = context.active_edge.edge

        with layout.container:
            with ui.column().classes("w-full gap-1 p-2"):
                ui.label("Connection Path").classes("font-semibold text-sm")
                ui.label(f"{edge.source_node_id} [{edge.outlet_port_id}]").classes("text-xs opacity-70")
                ui.label("↓").classes("text-xs opacity-50 ml-2")
                ui.label(f"{edge.sink_node_id} [{edge.inlet_port_id}]").classes("text-xs opacity-70")


@panel(
    editors="test_inspector",
    scopes="test_edge",
    label="Connection Warnings",
    icon=hui.icon.warning,
    order=5,
)
class TestEdgeWarningsPanel(BasePanel):
    @classmethod
    def poll(cls, context: "SessionContext") -> bool:
        state = _state(context)
        return state is not None and state.has_warning()

    def draw(self, context: "SessionContext", layout: PanelLayout) -> None:
        from nicegui import ui

        state = _state(context)
        if state is None:
            return

        with layout.container:
            with ui.column().classes("w-full gap-1 p-2"):
                ui.label("⚠ Warnings").classes("text-orange-500 font-semibold text-sm")
                for warning in state.warnings:
                    ui.label(f"• {warning}").classes(
                        "text-orange-400 text-xs whitespace-pre-wrap break-words ml-1"
                    )
