"""
Context menu panels for selection actions.

Phase 1.5: action=SelectionContextActions, focus=SelectionFocus.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haybale_studio.focuses import SelectionFocus
from haybale_studio.state.edit_state import EditState
from haywire.ui import elements as hui
from haybale_studio.editors.graph_canvas.handlers.context_menu_actions import SelectionContextActions
from haywire.ui.panel import Panel
from haywire.ui.panel.layout import PanelLayout
from haywire.ui.panel.decorator import panel

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext


@panel(
    action=SelectionContextActions,
    focus=SelectionFocus,
    label="Copy Selection",
    icon=hui.icon.copy,
    order=10,
)
class CopySelectionPanel(Panel):
    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        edit = ctx.data[EditState]
        return bool(edit.selected_nodes.value or edit.selected_edges.value)

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: SelectionContextActions,
    ) -> None:
        layout.button(
            "Copy Selection",
            icon=hui.icon.copy,
            on_click=actions.copy_selection,
        )


@panel(
    action=SelectionContextActions,
    focus=SelectionFocus,
    label="Paste",
    icon=hui.icon.paste,
    order=20,
)
class SelectionPasteSelectionPanel(Panel):
    """Paste panel under the selection focus.

    A separate CanvasPasteSelectionPanel lives in create_node_panel.py
    for the canvas-context popup. Both share the underlying paste action.
    """

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.data[EditState].clipboard.value is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: SelectionContextActions,
    ) -> None:
        layout.button(
            "Paste",
            icon=hui.icon.paste,
            on_click=actions.paste_at_click,
        )
