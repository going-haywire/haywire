"""Test-only node action panels for haybale_testing.

actions: TestNodeContextActions, focus=TestNodeFocus.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haybale_graph_editor.state.edit_state import EditState
from haybale_testing.test_actions import TestNodeContextActions
from haybale_testing.test_focuses import TestNodeFocus
from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel
from haywire.ui.panel.layout import PanelLayout
from haywire.ui.panel.decorator import panel

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


# --8<-- [start:test_delete_node_panel]
@panel(
    actions=TestNodeContextActions,
    focus=TestNodeFocus,
    label="Delete Node",
    icon=hui.icon.delete,
    order=10,
)
class TestDeleteNodePanel(BasePanel):
    actions: TestNodeContextActions

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
        layout.button(
            "Delete Node",
            icon=hui.icon.delete,
            on_click=lambda: self.actions.test_delete_node(node_id),
        )


# --8<-- [end:test_delete_node_panel]


@panel(
    actions=TestNodeContextActions,
    focus=TestNodeFocus,
    label="Copy Node",
    icon=hui.icon.copy,
    order=20,
)
class TestCopyNodePanel(BasePanel):
    actions: TestNodeContextActions

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
        layout.button(
            "Copy Node",
            icon=hui.icon.copy,
            on_click=lambda: self.actions.test_copy_node(node_id),
        )


@panel(
    actions=TestNodeContextActions,
    focus=TestNodeFocus,
    label="Redraw Node",
    icon=hui.icon.refresh,
    order=30,
)
class TestRedrawNodePanel(BasePanel):
    actions: TestNodeContextActions

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
        layout.button(
            "Redraw Node",
            icon=hui.icon.refresh,
            on_click=lambda: self.actions.test_redraw_node(node_id),
        )


@panel(
    actions=TestNodeContextActions,
    focus=TestNodeFocus,
    label="Revalidate Node",
    icon=hui.icon.refresh,
    order=40,
)
class TestRevalidateNodePanel(BasePanel):
    actions: TestNodeContextActions

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
        layout.button(
            "Revalidate Node",
            icon=hui.icon.refresh,
            on_click=lambda: self.actions.test_revalidate_node(node_id),
        )


@panel(
    actions=TestNodeContextActions,
    focus=TestNodeFocus,
    label="Reset Node",
    icon=hui.icon.reset,
    order=50,
)
class TestResetNodePanel(BasePanel):
    actions: TestNodeContextActions

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
        layout.button(
            "Reset Node",
            icon=hui.icon.reset,
            on_click=lambda: self.actions.test_reset_node(node_id),
        )
