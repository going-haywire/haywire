"""
Context menu panels for node actions.

actions: NodeContextActions, focus=NodeFocus.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haybale_studio.focuses import NodeFocus
from haybale_studio.state.edit_state import EditState
from haywire.ui import elements as hui
from haybale_studio.editors.graph_canvas.handlers.context_menu_actions import NodeContextActions
from haywire.ui.panel import BasePanel
from haywire.ui.panel.layout import PanelLayout
from haywire.ui.panel.decorator import panel

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


@panel(
    actions=NodeContextActions,
    focus=NodeFocus,
    label="Delete Node",
    icon=hui.icon.delete,
    order=10,
)
class DeleteNodePanel(BasePanel):
    actions: NodeContextActions

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
            on_click=lambda: self.actions.delete_node(node_id),
        )


@panel(
    actions=NodeContextActions,
    focus=NodeFocus,
    label="Copy Node",
    icon=hui.icon.copy,
    order=20,
)
class CopyNodePanel(BasePanel):
    actions: NodeContextActions

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
            on_click=lambda: self.actions.copy_node(node_id),
        )


@panel(
    actions=NodeContextActions,
    focus=NodeFocus,
    label="Redraw Node",
    icon=hui.icon.refresh,
    order=30,
)
class RedrawNodePanel(BasePanel):
    actions: NodeContextActions

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
            on_click=lambda: self.actions.redraw_node(node_id),
        )


@panel(
    actions=NodeContextActions,
    focus=NodeFocus,
    label="Revalidate Node",
    icon=hui.icon.node_status,
    order=40,
)
class RevalidateNodePanel(BasePanel):
    actions: NodeContextActions

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
            icon=hui.icon.node_status,
            on_click=lambda: self.actions.revalidate_node(node_id),
        )


@panel(
    actions=NodeContextActions,
    focus=NodeFocus,
    label="Reset Node",
    icon=hui.icon.reset,
    order=50,
)
class ResetNodePanel(BasePanel):
    actions: NodeContextActions

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
            on_click=lambda: self.actions.reset_node(node_id),
        )
