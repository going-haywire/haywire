"""
Test-only selection action panels for haybale_testing.

Uses editors="test_inspector", scopes="test_selection" to avoid
clashing with the production editor/scope namespace.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.ui.panel.base import BasePanel, PanelLayout
from haywire.ui.panel.decorator import panel

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext


def _emit(context: "SessionContext", event):
    fn = context.metadata.get("on_emit_event")
    if fn:
        fn(event)


@panel(
    registry_id="test_copy_selection",
    editors="test_inspector",
    scopes="test_selection",
    label="Copy Selection",
    icon="content_copy",
    order=10,
)
class TestCopySelectionPanel(BasePanel):
    @classmethod
    def poll(cls, context: "SessionContext") -> bool:
        return bool(context.selected_nodes or context.selected_edges)

    def draw(self, context: "SessionContext", layout: PanelLayout) -> None:
        from haywire.ui.graph_canvas.event_definitions import UserCopySelectedEvent

        def _copy():
            _emit(context, UserCopySelectedEvent(
                selectedNodes=list(context.selected_nodes),
                selectedEdges=list(context.selected_edges),
            ))

        layout.button("📋 Copy Selection", on_click=_copy)


@panel(
    registry_id="test_paste_selection",
    editors="test_inspector",
    scopes="test_selection",
    label="Paste",
    icon="content_paste",
    order=20,
)
class TestPasteSelectionPanel(BasePanel):
    @classmethod
    def poll(cls, context: "SessionContext") -> bool:
        clipboard = context.metadata.get("clipboard")
        return clipboard is not None and bool(getattr(clipboard, "nodes", None))

    def draw(self, context: "SessionContext", layout: PanelLayout) -> None:
        from haywire.ui.graph_canvas.event_definitions import UserPasteClipboardEvent

        canvas_x = context.metadata.get("canvas_x", 0)
        canvas_y = context.metadata.get("canvas_y", 0)

        def _paste():
            _emit(context, UserPasteClipboardEvent(canvasX=canvas_x, canvasY=canvas_y))

        layout.button("📄 Paste", on_click=_paste)
