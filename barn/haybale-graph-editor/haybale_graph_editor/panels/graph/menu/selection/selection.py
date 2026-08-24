# barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/selection/selection.py
"""
Selection context-menu panels — the surface ``SelectionMenu``.

These are also what the floating toolbar's ⋯ shows, since it hosts the same
surface rather than duplicating a curated set.

Every command here implements ``draw_disabled()``: an inapplicable command
greys rather than disappearing, which is the platform convention and matters
most here — this is the menu a user right-clicks into with an empty
selection. The label appears twice per panel because the panel owns both
renderings (a host-drawn row could not carry the dynamic "Copy 3 nodes"
form); a class constant is the whole answer.

Redraw / revalidate / reset sit one level down, on ``SelectionRebuildMenu``,
behind ``RebuildSelectionMenuPanel``'s "Rebuild" row: three commands of one
family, reached through one row instead of three.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel
from haywire.ui.panel.layout import PanelLayout
from haywire.ui.panel.decorator import panel

from .....surfaces import SelectionActions, SelectionMenu, SelectionRebuildMenu
from .....state.edit_state import EditState

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


def _selection_nonempty(ctx: "SessionContext") -> bool:
    edit = ctx.data[EditState]
    return bool(edit.selected_nodes or edit.selected_edges)


def _selection_counts(ctx: "SessionContext") -> tuple[int, int]:
    edit = ctx.data[EditState]
    return len(edit.selected_nodes), len(edit.selected_edges)

# SelectionMenu
#  -> CopySelectionMenuPanel
#  -> DeleteSelectionMenuPanel
#  -> RebuildSelectionMenuPanel
#     -> SelectionRebuildMenu
#        -> RedrawSelectionMenuPanel
#        -> RevalidateSelectionMenuPanel
#        -> ResetSelectionMenuPanel

@panel(
    surface=SelectionMenu,
    label="Copy Selection",
    icon=hui.icon.copy,
    order=10,
)
class CopySelectionMenuPanel(BasePanel):
    actions: SelectionActions

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
            hui.menu_row(
                selection_label("Copy", n_nodes, n_edges),
                icon=hui.icon.copy,
                on_click=self.actions.copy_selection,
            )

    def draw_disabled(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        """The static form, greyed — what the row should say with nothing selected."""
        with layout:
            hui.menu_row("Copy", icon=hui.icon.copy, enabled=False)


@panel(
    surface=SelectionMenu,
    label="Delete Selection",
    icon=hui.icon.delete,
    order=30,
)
class DeleteSelectionMenuPanel(BasePanel):
    """Delete every node and edge in the current selection in one undoable step."""

    actions: SelectionActions

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
            hui.menu_row(
                selection_label("Delete", n_nodes, n_edges),
                icon=hui.icon.delete,
                on_click=self.actions.delete_selection,
            )

    def draw_disabled(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        """The static form, greyed — what the row should say with nothing selected."""
        with layout:
            hui.menu_row("Delete", icon=hui.icon.delete, enabled=False)


@panel(
    surface=SelectionMenu,
    hosts=(SelectionRebuildMenu,),
    label="Rebuild",
    icon=hui.icon.refresh,
    order=40,
)
class RebuildSelectionMenuPanel(BasePanel):
    """The "Rebuild" row — a submenu over redraw / revalidate / reset.

    A hosting panel, so it draws only the arrangement: the row and the flyout
    it expands into. It pipes — the three commands inside reach the same
    ``SelectionActions`` host one hop further without either side naming it.
    """

    actions: SelectionActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return _selection_nonempty(ctx)

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        with layout:
            with hui.submenu_row("Rebuild", icon=hui.icon.refresh):
                self.render_surface(SelectionRebuildMenu, ctx)

    def draw_disabled(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        """The static form, greyed — a row that does not expand."""
        with layout:
            hui.submenu_row("Rebuild", icon=hui.icon.refresh, enabled=False)


@panel(
    surface=SelectionRebuildMenu,
    label="Redraw Selection",
    icon=hui.icon.refresh,
    order=10,
)
class RedrawSelectionMenuPanel(BasePanel):
    """Redraw every node/edge in the selection in one step."""

    actions: SelectionActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return _selection_nonempty(ctx)

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        n_nodes, n_edges = _selection_counts(ctx)
        with layout:
            hui.menu_row(
                selection_label("Redraw", n_nodes, n_edges),
                icon=hui.icon.refresh,
                on_click=self.actions.redraw_selection,
            )

    def draw_disabled(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        """The static form, greyed — what the row should say with nothing selected."""
        with layout:
            hui.menu_row("Redraw", icon=hui.icon.refresh, enabled=False)


@panel(
    surface=SelectionRebuildMenu,
    label="Revalidate Selection",
    icon=hui.icon.node_status,
    order=20,
)
class RevalidateSelectionMenuPanel(BasePanel):
    """Revalidate every node/edge in the selection in one step."""

    actions: SelectionActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return _selection_nonempty(ctx)

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        n_nodes, n_edges = _selection_counts(ctx)
        with layout:
            hui.menu_row(
                selection_label("Revalidate", n_nodes, n_edges),
                icon=hui.icon.node_status,
                on_click=self.actions.revalidate_selection,
            )

    def draw_disabled(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        """The static form, greyed — what the row should say with nothing selected."""
        with layout:
            hui.menu_row("Revalidate", icon=hui.icon.node_status, enabled=False)


@panel(
    surface=SelectionRebuildMenu,
    label="Reset Selection",
    icon=hui.icon.reset,
    order=30,
)
class ResetSelectionMenuPanel(BasePanel):
    """Reset every node/edge in the selection in one step."""

    actions: SelectionActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return _selection_nonempty(ctx)

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        n_nodes, n_edges = _selection_counts(ctx)
        with layout:
            hui.menu_row(
                selection_label("Reset", n_nodes, n_edges),
                icon=hui.icon.reset,
                on_click=self.actions.reset_selection,
            )

    def draw_disabled(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        """The static form, greyed — what the row should say with nothing selected."""
        with layout:
            hui.menu_row("Reset", icon=hui.icon.reset, enabled=False)


def _node_has_errors(ctx: "SessionContext") -> bool:
    node = ctx.data[EditState].active_node
    return node is not None and bool(node.state.get_errors())


def _render_node_errors(ctx: "SessionContext", layout: PanelLayout) -> None:
    from haywire.ui.errors.error_info import error_render_detail

    node = ctx.data[EditState].active_node
    if node is None:
        return
    errors = node.state.get_errors()
    if not errors:
        return
    with layout.container:
        for error in errors:
            error_render_detail(error)


@panel(
    surface=SelectionMenu,
    label="Node Errors",
    icon=hui.icon.error,
    order=0,
)
class NodeErrorsSelectionMenuPanel(BasePanel):
    """Node errors panel for the unified selection context menu.

    Scoped to the primary (active) node's errors via _node_has_errors, which
    reads EditState.active_node — set by on_selection_context to the
    selection's primary. Display-only; calls no action verb.
    """

    actions: SelectionActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return _node_has_errors(ctx)

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        _render_node_errors(ctx, layout)


@panel(
    surface=SelectionMenu,
    label="Dissolve Reroute",
    icon=hui.icon.edge,
    order=15,
)
class DissolveRerouteMenuPanel(BasePanel):
    """Collapse a reroute node back into a direct connection.

    Only visible when the right-clicked node is a reroute node.
    Bridges the upstream outlet directly to every downstream inlet,
    then removes the reroute — all as one undoable operation.
    """

    actions: SelectionActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        wrapper = ctx.data[EditState].active_node
        if wrapper is None:
            return False
        return wrapper.node.behavior.is_reroute_node

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        wrapper = ctx.data[EditState].active_node
        if wrapper is None:
            return
        node_id = wrapper.node_id

        with layout:
            hui.menu_row(
                "Dissolve Reroute",
                icon=hui.icon.edge,
                on_click=lambda: self.actions.dissolve_reroute(node_id),
            )
