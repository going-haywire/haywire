"""
Context menu panels for node actions.

Phase 1.5 of the panel-contract migration. action=NodeContextActions,
focus=NodeFocus.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haybale_studio.focuses import NodeFocus
from haywire.ui import elements as hui
from haywire.ui.graph_canvas.handlers.context_menu_actions import NodeContextActions
from haywire.ui.panel import Panel
from haywire.ui.panel.layout import PanelLayout
from haywire.ui.panel.decorator import panel

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext


@panel(
    action=NodeContextActions,
    focus=NodeFocus,
    label="Delete Node",
    icon=hui.icon.delete,
    order=10,
)
class DeleteNodePanel(Panel):
    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.active_node.value is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: NodeContextActions,
    ) -> None:
        node = ctx.active_node.value
        if node is None:
            return
        node_id = node.node_id
        layout.button(
            "Delete Node",
            icon=hui.icon.delete,
            on_click=lambda: actions.delete_node(node_id),
        )


@panel(
    action=NodeContextActions,
    focus=NodeFocus,
    label="Copy Node",
    icon=hui.icon.copy,
    order=20,
)
class CopyNodePanel(Panel):
    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.active_node.value is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: NodeContextActions,
    ) -> None:
        node = ctx.active_node.value
        if node is None:
            return
        node_id = node.node_id
        layout.button(
            "Copy Node",
            icon=hui.icon.copy,
            on_click=lambda: actions.copy_node(node_id),
        )


@panel(
    action=NodeContextActions,
    focus=NodeFocus,
    label="Redraw Node",
    icon=hui.icon.refresh,
    order=30,
)
class RedrawNodePanel(Panel):
    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.active_node.value is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: NodeContextActions,
    ) -> None:
        node = ctx.active_node.value
        if node is None:
            return
        node_id = node.node_id
        layout.button(
            "Redraw Node",
            icon=hui.icon.refresh,
            on_click=lambda: actions.redraw_node(node_id),
        )


@panel(
    action=NodeContextActions,
    focus=NodeFocus,
    label="Revalidate Node",
    icon=hui.icon.node_status,
    order=40,
)
class RevalidateNodePanel(Panel):
    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.active_node.value is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: NodeContextActions,
    ) -> None:
        node = ctx.active_node.value
        if node is None:
            return
        node_id = node.node_id
        layout.button(
            "Revalidate Node",
            icon=hui.icon.node_status,
            on_click=lambda: actions.revalidate_node(node_id),
        )


@panel(
    action=NodeContextActions,
    focus=NodeFocus,
    label="Reset Node",
    icon=hui.icon.reset,
    order=50,
)
class ResetNodePanel(Panel):
    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.active_node.value is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: NodeContextActions,
    ) -> None:
        node = ctx.active_node.value
        if node is None:
            return
        node_id = node.node_id
        layout.button(
            "Reset Node",
            icon=hui.icon.reset,
            on_click=lambda: actions.reset_node(node_id),
        )
