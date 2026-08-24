"""Test-only node action panels for haybale_testing.

On the ``TestNodeMenu`` surface.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haybale_graph_editor.state.edit_state import EditState
from haybale_testing.surfaces import TestNodeActions, TestNodeMenu
from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel
from haywire.ui.panel.layout import PanelLayout
from haywire.ui.panel.decorator import panel

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


@panel(
    surface=TestNodeMenu,
    label="Delete Node",
    icon=hui.icon.delete,
    order=10,
)
class TestDeleteNodeMenuPanel(BasePanel):
    actions: TestNodeActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.data[EditState].active_node is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        node = ctx.data[EditState].active_node
        if node is None:
            return
        node_id = node.node_id
        with layout:
            hui.button(
                "Delete Node",
                icon=hui.icon.delete,
                on_click=lambda: self.actions.test_delete_node(node_id),
            )


@panel(
    surface=TestNodeMenu,
    label="Copy Node",
    icon=hui.icon.copy,
    order=20,
)
class TestCopyNodeMenuPanel(BasePanel):
    actions: TestNodeActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.data[EditState].active_node is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        node = ctx.data[EditState].active_node
        if node is None:
            return
        node_id = node.node_id
        with layout:
            hui.button(
                "Copy Node",
                icon=hui.icon.copy,
                on_click=lambda: self.actions.test_copy_node(node_id),
            )


@panel(
    surface=TestNodeMenu,
    label="Redraw Node",
    icon=hui.icon.refresh,
    order=30,
)
class TestRedrawNodeMenuPanel(BasePanel):
    actions: TestNodeActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.data[EditState].active_node is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        node = ctx.data[EditState].active_node
        if node is None:
            return
        node_id = node.node_id
        with layout:
            hui.button(
                "Redraw Node",
                icon=hui.icon.refresh,
                on_click=lambda: self.actions.test_redraw_node(node_id),
            )


@panel(
    surface=TestNodeMenu,
    label="Revalidate Node",
    icon=hui.icon.refresh,
    order=40,
)
class TestRevalidateNodeMenuPanel(BasePanel):
    actions: TestNodeActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.data[EditState].active_node is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        node = ctx.data[EditState].active_node
        if node is None:
            return
        node_id = node.node_id
        with layout:
            hui.button(
                "Revalidate Node",
                icon=hui.icon.refresh,
                on_click=lambda: self.actions.test_revalidate_node(node_id),
            )


@panel(
    surface=TestNodeMenu,
    label="Reset Node",
    icon=hui.icon.reset,
    order=50,
)
class TestResetNodeMenuPanel(BasePanel):
    actions: TestNodeActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.data[EditState].active_node is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        node = ctx.data[EditState].active_node
        if node is None:
            return
        node_id = node.node_id
        with layout:
            hui.button(
                "Reset Node",
                icon=hui.icon.reset,
                on_click=lambda: self.actions.test_reset_node(node_id),
            )
