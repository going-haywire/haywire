"""
Context menu panels for selection actions.

actions: SelectionContextActions, focus=SelectionFocus.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel
from haywire.ui.panel.layout import PanelLayout
from haywire.ui.panel.decorator import panel

from ...focuses import SelectionFocus
from ...state.edit_state import EditState
from ...editors.graph_canvas.handlers.context_menu_actions import SelectionContextActions

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


@panel(
    actions=SelectionContextActions,
    focus=SelectionFocus,
    label="Copy Selection",
    icon=hui.icon.copy,
    order=10,
)
class CopySelectionPanel(BasePanel):
    actions: SelectionContextActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        edit = ctx.data[EditState]
        return bool(edit.selected_nodes or edit.selected_edges)

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        layout.button(
            "Copy Selection",
            icon=hui.icon.copy,
            on_click=self.actions.copy_selection,
        )


@panel(
    actions=SelectionContextActions,
    focus=SelectionFocus,
    label="Paste",
    icon=hui.icon.paste,
    order=20,
)
class SelectionPasteSelectionPanel(BasePanel):
    """Paste panel under the selection focus.

    A separate CanvasPasteSelectionPanel lives in create_node_panel.py
    for the canvas-context popup. Both share the underlying paste action.
    """

    actions: SelectionContextActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.data[EditState].clipboard is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        layout.button(
            "Paste",
            icon=hui.icon.paste,
            on_click=self.actions.paste_at_click,
        )
