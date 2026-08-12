# barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/selection/selection.py
"""
Selection context-menu panels.

actions: SelectionContextActions, focus=SelectionFocus.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel
from haywire.ui.panel.layout import PanelLayout
from haywire.ui.panel.decorator import panel

from .....focuses import SelectionFocus
from .....state.edit_state import EditState
from .....editors.graph_canvas.handlers.context_menu_actions import SelectionContextActions

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


@panel(
    actions=SelectionContextActions,
    focus=SelectionFocus,
    label="Copy Selection",
    icon=hui.icon.copy,
    order=10,
)
class CopySelectionMenuPanel(BasePanel):
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
class DeleteSelectionMenuPanel(BasePanel):
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




@panel(
    actions=SelectionContextActions,
    focus=SelectionFocus,
    label="Redraw Selection",
    icon=hui.icon.refresh,
    order=40,
)
class RedrawSelectionMenuPanel(BasePanel):
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
class RevalidateSelectionMenuPanel(BasePanel):
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
class ResetSelectionMenuPanel(BasePanel):
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
    actions=SelectionContextActions,
    focus=SelectionFocus,
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

    actions: SelectionContextActions

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
    actions=SelectionContextActions,
    focus=SelectionFocus,
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

    actions: SelectionContextActions

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
            hui.button(
                "Dissolve Reroute",
                icon=hui.icon.edge,
                on_click=lambda: self.actions.dissolve_reroute(node_id),
            )
