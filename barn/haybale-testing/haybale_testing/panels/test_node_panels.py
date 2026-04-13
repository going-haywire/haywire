"""
Test-only node action panels for haybale_testing.

Uses editors="test_inspector", scopes="test_node" to avoid
clashing with the production editor/scope namespace.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.ui.panel.base import BasePanel, PanelLayout
from haywire.ui.panel.decorator import panel
from haywire.ui import elements as hui

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext


def _emit(context: "SessionContext", event):
    fn = context.metadata.get("on_emit_event")
    if fn:
        fn(event)


@panel(
    editors="test_inspector",
    scopes="test_node",
    label="Delete Node",
    icon="delete",
    order=10,
)
class TestDeleteNodePanel(BasePanel):
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
    editors="test_inspector",
    scopes="test_node",
    label="Copy Node",
    icon=hui.icon.copy,
    order=20,
)
class TestCopyNodePanel(BasePanel):
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
    editors="test_inspector",
    scopes="test_node",
    label="Redraw Node",
    icon=hui.icon.refresh,
    order=30,
)
class TestRedrawNodePanel(BasePanel):
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
    editors="test_inspector",
    scopes="test_node",
    label="Revalidate Node",
    icon=hui.icon.refresh,
    order=40,
)
class TestRevalidateNodePanel(BasePanel):
    @classmethod
    def poll(cls, context: "SessionContext") -> bool:
        return context.active_node is not None

    def draw(self, context: "SessionContext", layout: PanelLayout) -> None:
        from haywire.ui.graph_canvas.event_definitions import ElementRevalidateEvent

        node_id = context.active_node.node_id

        def _revalidate():
            _emit(context, ElementRevalidateEvent(nodes=[node_id], edges=[]))

        layout.button("Revalidate Node", icon=hui.icon.refresh, on_click=_revalidate)


@panel(
    editors="test_inspector",
    scopes="test_node",
    label="Reset Node",
    icon=hui.icon.reset,
    order=50,
)
class TestResetNodePanel(BasePanel):
    @classmethod
    def poll(cls, context: "SessionContext") -> bool:
        return context.active_node is not None

    def draw(self, context: "SessionContext", layout: PanelLayout) -> None:
        from haywire.ui.graph_canvas.event_definitions import ElementResetEvent

        node_id = context.active_node.node_id

        def _reset():
            _emit(context, ElementResetEvent(nodes=[node_id], edges=[]))

        layout.button("Reset Node", icon=hui.icon.reset, on_click=_reset)
