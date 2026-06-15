"""
Floating toolbar panels for the graph canvas (ToolbarFocus).

Each panel contributes a single icon-only button.
The provider (Task 5) owns the ui.row container; each panel just renders one hui.icon_action.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel
from haywire.ui.panel.layout import PanelLayout
from haywire.ui.panel.decorator import panel

from ...focuses import ToolbarFocus
from ...state.edit_state import EditState
from ...editors.graph_canvas.handlers.context_menu_actions import (
    SelectionContextActions,
    ToolbarActions,
)

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


@panel(
    actions=SelectionContextActions,
    focus=ToolbarFocus,
    label="Copy",
    icon=hui.icon.copy,
    order=10,
)
class CopyToolbarPanel(BasePanel):
    actions: SelectionContextActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        edit = ctx.data[EditState]
        return bool(edit.selected_nodes or edit.selected_edges)

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        with layout:
            hui.icon_action(hui.icon.copy, tooltip="Copy", on_click=self.actions.copy_selection)


@panel(
    actions=SelectionContextActions,
    focus=ToolbarFocus,
    label="Delete",
    icon=hui.icon.delete,
    order=20,
)
class DeleteToolbarPanel(BasePanel):
    actions: SelectionContextActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        edit = ctx.data[EditState]
        return bool(edit.selected_nodes or edit.selected_edges)

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        with layout:
            hui.icon_action(hui.icon.delete, tooltip="Delete", on_click=self.actions.delete_selection)


@panel(
    actions=ToolbarActions,
    focus=ToolbarFocus,
    label="More",
    icon="more_horiz",
    order=900,
)
class OverflowToolbarPanel(BasePanel):
    actions: ToolbarActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        edit = ctx.data[EditState]
        return bool(edit.selected_nodes or edit.selected_edges)

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        with layout:
            hui.icon_action("more_horiz", tooltip="More actions", on_click=self.actions.open_overflow_menu)
