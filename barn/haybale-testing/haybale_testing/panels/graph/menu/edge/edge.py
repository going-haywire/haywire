"""Test-only edge action panels for haybale_testing.

On the ``TestEdgeMenu`` surface.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haybale_graph_editor.state.edit_state import EditState
from haybale_testing.surfaces import TestEdgeActions, TestEdgeMenu
from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel
from haywire.ui.panel.layout import PanelLayout
from haywire.ui.panel.decorator import panel

if TYPE_CHECKING:
    from haywire.core.edge.edge_wrapper import EdgeWrapperState
    from haywire.core.session.context import SessionContext


def _state(ctx: "SessionContext") -> "EdgeWrapperState | None":
    wrapper = ctx.data[EditState].active_edge
    return wrapper.get_state() if wrapper is not None else None


@panel(
    surface=TestEdgeMenu,
    label="Delete Connection",
    icon=hui.icon.delete,
    order=10,
)
class TestDeleteEdgeMenuPanel(BasePanel):
    actions: TestEdgeActions

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
        with layout:
            hui.button(
                "Delete Connection",
                icon=hui.icon.delete,
                on_click=lambda: self.actions.test_delete_edge(edge_id),
            )


@panel(
    surface=TestEdgeMenu,
    label="Inspect Connection",
    icon=hui.icon.node_info,
    order=20,
)
class TestInspectEdgeMenuPanel(BasePanel):
    actions: TestEdgeActions

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
        with layout:
            hui.button(
                "Inspect Connection",
                icon=hui.icon.node_info,
                on_click=lambda: self.actions.test_inspect_edge(edge_id),
            )


@panel(
    surface=TestEdgeMenu,
    label="Connection Errors",
    icon=hui.icon.error,
    order=0,
)
class TestEdgeErrorsMenuPanel(BasePanel):
    actions: TestEdgeActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        state = _state(ctx)
        return state is not None and state.get_error() is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        from haywire.core.errors.haywire_exception import HaywireException
        from haywire.ui.errors.error_info import error_render_detail

        state = _state(ctx)
        error = state.get_error() if state else None
        if error is None:
            return

        with layout:
            if isinstance(error, HaywireException):
                hui.info_row("Category", str(error.category))
                error_render_detail(error)
            else:
                hui.error_label(str(error)).classes("whitespace-pre-wrap break-words")


@panel(
    surface=TestEdgeMenu,
    label="Connection Path",
    icon=hui.icon.adapter,
    order=15,
)
class TestEdgePathMenuPanel(BasePanel):
    actions: TestEdgeActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        wrapper = ctx.data[EditState].active_edge
        return wrapper is not None and wrapper.edge is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        wrapper = ctx.data[EditState].active_edge
        if wrapper is None or wrapper.edge is None:
            return
        edge = wrapper.edge

        with layout:
            hui.info_row("From", f"{edge.source_node_id}[{edge.outlet_port_id}]")
            hui.info_row("To", f"{edge.sink_node_id}[{edge.inlet_port_id}]")


@panel(
    surface=TestEdgeMenu,
    label="Connection Warnings",
    icon=hui.icon.warning,
    order=5,
)
class TestEdgeWarningsMenuPanel(BasePanel):
    actions: TestEdgeActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        state = _state(ctx)
        return state is not None and state.has_warning()

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        state = _state(ctx)
        if state is None:
            return

        with layout:
            hui.warning_label("Warnings").classes("font-semibold")
            for warning in state.warnings:
                hui.warning_label(f"• {warning}").classes("whitespace-pre-wrap break-words ml-1")
