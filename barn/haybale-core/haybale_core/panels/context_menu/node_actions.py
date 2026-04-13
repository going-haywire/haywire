"""
Context menu panels for node actions.

Contributed to editor='context_menu', scope='node'.
Each panel emits the corresponding canvas event via ctx.metadata['on_emit_event'].
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.ui import elements as hui
from haywire.ui.panel.base import BasePanel, PanelLayout
from haywire.ui.panel.decorator import panel

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext


def _emit(context: "SessionContext", event):
    fn = context.metadata.get("on_emit_event")
    if fn:
        fn(event)


@panel(
    editors="context_menu",
    scopes="node",
    label="Delete Node",
    icon=hui.icon.delete,
    order=10,
)
class DeleteNodePanel(BasePanel):
    @classmethod
    def poll(cls, context: "SessionContext") -> bool:
        return context.active_node is not None

    def draw(self, context: "SessionContext", layout: PanelLayout) -> None:
        from haywire.ui.graph_canvas.event_definitions import UserRemoveEvent

        node_id = context.active_node.node_id

        def _delete():
            _emit(context, UserRemoveEvent(nodes=[node_id], edges=[]))

        layout.button("Delete Node", icon=hui.icon.delete, on_click=_delete)


@panel(
    editors="context_menu",
    scopes="node",
    label="Copy Node",
    icon=hui.icon.copy,
    order=20,
)
class CopyNodePanel(BasePanel):
    @classmethod
    def poll(cls, context: "SessionContext") -> bool:
        return context.active_node is not None

    def draw(self, context: "SessionContext", layout: PanelLayout) -> None:
        from haywire.ui.graph_canvas.event_definitions import UserCopySelectedEvent

        node_id = context.active_node.node_id

        def _copy():
            _emit(context, UserCopySelectedEvent(selectedNodes=[node_id], selectedEdges=[]))

        layout.button("Copy Node", icon=hui.icon.copy, on_click=_copy)


@panel(
    editors="context_menu",
    scopes="node",
    label="Redraw Node",
    icon=hui.icon.refresh,
    order=30,
)
class RedrawNodePanel(BasePanel):
    @classmethod
    def poll(cls, context: "SessionContext") -> bool:
        return context.active_node is not None

    def draw(self, context: "SessionContext", layout: PanelLayout) -> None:
        from haywire.ui.graph_canvas.event_definitions import ElementRedrawEvent

        node_id = context.active_node.node_id

        def _redraw():
            _emit(context, ElementRedrawEvent(nodes=[node_id], edges=[]))

        layout.button("Redraw Node", icon=hui.icon.refresh, on_click=_redraw)


@panel(
    editors="context_menu",
    scopes="node",
    label="Revalidate Node",
    icon=hui.icon.node_status,
    order=40,
)
class RevalidateNodePanel(BasePanel):
    @classmethod
    def poll(cls, context: "SessionContext") -> bool:
        return context.active_node is not None

    def draw(self, context: "SessionContext", layout: PanelLayout) -> None:
        from haywire.ui.graph_canvas.event_definitions import ElementRevalidateEvent

        node_id = context.active_node.node_id

        def _revalidate():
            _emit(context, ElementRevalidateEvent(nodes=[node_id], edges=[]))

        layout.button("Revalidate Node", icon=hui.icon.node_status, on_click=_revalidate)


@panel(
    editors="context_menu",
    scopes="node",
    label="Reset Node",
    icon=hui.icon.reset,
    order=50,
)
class ResetNodePanel(BasePanel):
    @classmethod
    def poll(cls, context: "SessionContext") -> bool:
        return context.active_node is not None

    def draw(self, context: "SessionContext", layout: PanelLayout) -> None:
        from haywire.ui.graph_canvas.event_definitions import ElementResetEvent

        node_id = context.active_node.node_id

        def _reset():
            _emit(context, ElementResetEvent(nodes=[node_id], edges=[]))

        layout.button("Reset Node", icon=hui.icon.reset, on_click=_reset)
