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


def selection_label(verb: str, n_nodes: int, n_edges: int) -> str:
    """Count-aware command label.

    1 node  -> "<verb> Node";   n nodes -> "<verb> n Nodes"
    1 edge  -> "<verb> Edge";   n edges -> "<verb> n Edges"
    mixed   -> "<verb> Selection"
    """
    if n_nodes and n_edges:
        return f"{verb} Selection"
    if n_nodes:
        return f"{verb} Node" if n_nodes == 1 else f"{verb} {n_nodes} Nodes"
    if n_edges:
        return f"{verb} Edge" if n_edges == 1 else f"{verb} {n_edges} Edges"
    return f"{verb} Selection"


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
        n_nodes, n_edges = _selection_counts(ctx)
        with layout:
            hui.button(
                selection_label("Copy", n_nodes, n_edges),
                icon=hui.icon.copy,
                on_click=self.actions.copy_selection,
            )


@panel(
    actions=SelectionContextActions,
    focus=SelectionFocus,
    label="Delete Selection",
    icon=hui.icon.delete,
    order=30,
)
class DeleteSelectionPanel(BasePanel):
    """Delete every node and edge in the current selection in one undoable step."""

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
        n_nodes, n_edges = _selection_counts(ctx)
        with layout:
            hui.button(
                selection_label("Delete", n_nodes, n_edges),
                icon=hui.icon.delete,
                on_click=self.actions.delete_selection,
            )


def _selection_nonempty(ctx: "SessionContext") -> bool:
    edit = ctx.data[EditState]
    return bool(edit.selected_nodes or edit.selected_edges)


def _selection_counts(ctx: "SessionContext") -> tuple[int, int]:
    edit = ctx.data[EditState]
    return len(edit.selected_nodes), len(edit.selected_edges)


@panel(
    actions=SelectionContextActions,
    focus=SelectionFocus,
    label="Redraw Selection",
    icon=hui.icon.refresh,
    order=40,
)
class RedrawSelectionPanel(BasePanel):
    """Redraw every node/edge in the selection in one step."""

    actions: SelectionContextActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return _selection_nonempty(ctx)

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        n_nodes, n_edges = _selection_counts(ctx)
        with layout:
            hui.button(
                selection_label("Redraw", n_nodes, n_edges),
                icon=hui.icon.refresh,
                on_click=self.actions.redraw_selection,
            )


@panel(
    actions=SelectionContextActions,
    focus=SelectionFocus,
    label="Revalidate Selection",
    icon=hui.icon.node_status,
    order=50,
)
class RevalidateSelectionPanel(BasePanel):
    """Revalidate every node/edge in the selection in one step."""

    actions: SelectionContextActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return _selection_nonempty(ctx)

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        n_nodes, n_edges = _selection_counts(ctx)
        with layout:
            hui.button(
                selection_label("Revalidate", n_nodes, n_edges),
                icon=hui.icon.node_status,
                on_click=self.actions.revalidate_selection,
            )


@panel(
    actions=SelectionContextActions,
    focus=SelectionFocus,
    label="Reset Selection",
    icon=hui.icon.reset,
    order=60,
)
class ResetSelectionPanel(BasePanel):
    """Reset every node/edge in the selection in one step."""

    actions: SelectionContextActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return _selection_nonempty(ctx)

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        n_nodes, n_edges = _selection_counts(ctx)
        with layout:
            hui.button(
                selection_label("Reset", n_nodes, n_edges),
                icon=hui.icon.reset,
                on_click=self.actions.reset_selection,
            )
