"""Test-only node action panels for haybale_testing.

Phase 1.5: action=TestNodeContextActions, focus=TestNodeFocus.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haybale_studio.state.edit_state import EditState
from haybale_testing.test_actions import TestNodeContextActions
from haybale_testing.test_focuses import TestNodeFocus
from haywire.ui import elements as hui
from haywire.ui.panel import Panel
from haywire.ui.panel.layout import PanelLayout
from haywire.ui.panel.decorator import panel

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext


@panel(
    action=TestNodeContextActions,
    focus=TestNodeFocus,
    label="Delete Node",
    icon=hui.icon.delete,
    order=10,
)
class TestDeleteNodePanel(Panel):
    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.data[EditState].active_node.value is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: TestNodeContextActions,
    ) -> None:
        node = ctx.data[EditState].active_node.value
        if node is None:
            return
        node_id = node.node_id
        layout.button(
            "Delete Node",
            icon=hui.icon.delete,
            on_click=lambda: actions.test_delete_node(node_id),
        )


@panel(
    action=TestNodeContextActions,
    focus=TestNodeFocus,
    label="Copy Node",
    icon=hui.icon.copy,
    order=20,
)
class TestCopyNodePanel(Panel):
    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.data[EditState].active_node.value is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: TestNodeContextActions,
    ) -> None:
        node = ctx.data[EditState].active_node.value
        if node is None:
            return
        node_id = node.node_id
        layout.button(
            "Copy Node",
            icon=hui.icon.copy,
            on_click=lambda: actions.test_copy_node(node_id),
        )


@panel(
    action=TestNodeContextActions,
    focus=TestNodeFocus,
    label="Redraw Node",
    icon=hui.icon.refresh,
    order=30,
)
class TestRedrawNodePanel(Panel):
    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.data[EditState].active_node.value is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: TestNodeContextActions,
    ) -> None:
        node = ctx.data[EditState].active_node.value
        if node is None:
            return
        node_id = node.node_id
        layout.button(
            "Redraw Node",
            icon=hui.icon.refresh,
            on_click=lambda: actions.test_redraw_node(node_id),
        )


@panel(
    action=TestNodeContextActions,
    focus=TestNodeFocus,
    label="Revalidate Node",
    icon=hui.icon.refresh,
    order=40,
)
class TestRevalidateNodePanel(Panel):
    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.data[EditState].active_node.value is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: TestNodeContextActions,
    ) -> None:
        node = ctx.data[EditState].active_node.value
        if node is None:
            return
        node_id = node.node_id
        layout.button(
            "Revalidate Node",
            icon=hui.icon.refresh,
            on_click=lambda: actions.test_revalidate_node(node_id),
        )


@panel(
    action=TestNodeContextActions,
    focus=TestNodeFocus,
    label="Reset Node",
    icon=hui.icon.reset,
    order=50,
)
class TestResetNodePanel(Panel):
    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.data[EditState].active_node.value is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: TestNodeContextActions,
    ) -> None:
        node = ctx.data[EditState].active_node.value
        if node is None:
            return
        node_id = node.node_id
        layout.button(
            "Reset Node",
            icon=hui.icon.reset,
            on_click=lambda: actions.test_reset_node(node_id),
        )
