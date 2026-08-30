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

from nicegui import ui

from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel
from haywire.ui.panel.layout import PanelLayout
from haywire.ui.panel.decorator import panel

from .....surfaces import (
    SelectionActions,
    SelectionDetailMenu,
    SelectionMenu,
    SelectionRebuildMenu,
)
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


# ---------------------------------------------------------------------------
# Card density — the ADR-0032 axes, applied across the selection.
#
#  SelectionMenu
#   -> CollapseSelectionMenuPanel      (a toggle, so a top-level row)
#   -> DetailSelectionMenuPanel
#      -> SelectionDetailMenu
#         -> DetailRankMenuPanel       (one row per NodeDetail rank)
#         -> ClearDetailOverridesMenuPanel
#
# Why here and not only on the floating toolbar: the toolbar appears on
# selection, whereas the context menu is where a user looks for "do something
# to this node". Right-clicking an unselected node replaces the selection with
# it first (canvas.vue's replace-then-act), so both surfaces act on the same
# set — the menu buys reach-by-habit and one entry for a whole multi-selection,
# not access the toolbar lacks.
#
# `detail` also renders live in the toolbar's Appearance dropdown already,
# since that draws the props bag's `appearance` category and detail sits in
# it. These rows are the command form of the same write.


def _selected_nodes_only(ctx: "SessionContext") -> bool:
    """True when the selection holds at least one NODE.

    Edges have no card, so an edge-only selection must not offer either axis —
    the commands would poll true and then do nothing.
    """
    return bool(ctx.data[EditState].selected_nodes)


@panel(
    surface=SelectionMenu,
    label="Collapse",
    icon=hui.icon.node_collapse,
    order=45,
)
class CollapseSelectionMenuPanel(BasePanel):
    """Fold or unfold every selected node — one row, both directions.

    **The row rewrites itself on click rather than closing over its state.**
    ``hui.menu_row`` does not dismiss its popup, so this menu is still on
    screen after the command runs: a handler that captured ``collapsed`` at
    draw time would keep re-sending that same value, and the toggle would work
    exactly once. It did, until it was found. The current state is asked for on
    every click (``toggle_selection_collapsed`` decides server-side and returns
    the new state), and the label and icon are updated in place from the
    answer, so what the row says stays true while the menu remains open.

    The icon names the action, not the state — it pairs with the label, which
    also says the verb. An icon showing the *current* state beside a label
    saying the *next* one reads as a contradiction.
    """

    actions: SelectionActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return _selected_nodes_only(ctx)

    @staticmethod
    def _row_text(collapsed: bool, n_nodes: int) -> str:
        return selection_label("Expand" if collapsed else "Collapse", n_nodes, 0)

    @staticmethod
    def _row_icon(collapsed: bool) -> str:
        return hui.icon.node_expand if collapsed else hui.icon.node_collapse

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        n_nodes = len(ctx.data[EditState].selected_nodes)
        collapsed = self.actions.selection_is_collapsed()

        with layout:
            row = hui.menu_row(self._row_text(collapsed, n_nodes), icon=self._row_icon(collapsed))

        # Reach into the row this panel just built to relabel it after a click.
        # menu_row's shape is (icon?, label) and it always makes both here,
        # since an icon was passed — but read them defensively rather than by
        # index, so a change to that shape degrades to "the row stops
        # relabelling" instead of raising out of a click handler.
        icon_el = next((c for c in row.default_slot.children if isinstance(c, ui.icon)), None)
        label_el = next((c for c in row.default_slot.children if isinstance(c, ui.label)), None)

        def _toggle() -> None:
            now_collapsed = self.actions.toggle_selection_collapsed()
            if label_el is not None:
                label_el.set_text(self._row_text(now_collapsed, n_nodes))
            if icon_el is not None:
                icon_el.set_name(self._row_icon(now_collapsed))

        row.on("click", lambda _e=None: _toggle())

    def draw_disabled(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        with layout:
            hui.menu_row("Collapse", icon=hui.icon.node_collapse, enabled=False)


@panel(
    surface=SelectionMenu,
    hosts=(SelectionDetailMenu,),
    label="Detail",
    icon=hui.icon.node_detail,
    order=46,
)
class DetailSelectionMenuPanel(BasePanel):
    """The "Detail" row — a submenu over the density ranks.

    A hosting panel: it draws only the row and the flyout, and pipes the
    ``SelectionActions`` host one hop further to the rows inside.
    """

    actions: SelectionActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return _selected_nodes_only(ctx)

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        with layout:
            with hui.submenu_row("Detail", icon=hui.icon.node_detail):
                self.render_surface(SelectionDetailMenu, ctx)

    def draw_disabled(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        with layout:
            hui.menu_row("Detail", icon=hui.icon.node_detail, enabled=False)


@panel(
    surface=SelectionDetailMenu,
    label="Detail Ranks",
    icon=hui.icon.node_detail,
    order=10,
)
class DetailRankMenuPanel(BasePanel):
    """One row per ``NodeDetail`` rank, built from the enum rather than listed.

    Deriving the rows means a rank added later appears here without anyone
    remembering to come back — the same reason the settings widget builds its
    options from the enum.
    """

    actions: SelectionActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return _selected_nodes_only(ctx)

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        from haywire.core.types import NodeDetail

        with layout:
            for rank in NodeDetail:
                hui.menu_row(
                    rank.label,
                    icon=hui.icon.node_detail,
                    on_click=lambda r=rank: self.actions.set_selection_detail(r.value),
                )

    def draw_disabled(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        from haywire.core.types import NodeDetail

        with layout:
            for rank in NodeDetail:
                hui.menu_row(rank.label, icon=hui.icon.node_detail, enabled=False)


# TOP LEVEL, beside the two rows it undoes — not inside Detail.
#
# It lived under Detail first, which put the only way to un-pin a *folded* node
# two levels down inside a submenu about density. Moving it up is what makes the
# label true of its position as well as its effect: it resets BOTH axes, so it
# belongs beside both, not under one of them.
#
# The alternative considered and rejected: a second copy under Collapse. That
# needs a submenu row that is also clickable, which `hui.submenu_row` is not,
# and duplicating a destructive-ish command is worse than moving it.
_FOLLOW_GRAPH_LABEL = "Reset Detail & Collapse"
_FOLLOW_GRAPH_TOOLTIP = "Clear this node's own detail and collapse so both follow the graph again"


@panel(
    surface=SelectionMenu,
    label=_FOLLOW_GRAPH_LABEL,
    icon=hui.icon.reset,
    order=47,
)
class ClearDetailOverridesMenuPanel(BasePanel):
    """Drop each selected node's own answer on BOTH card axes, so it tracks its
    graph again.

    Without this a node that has ever been folded or re-ranked by hand is
    pinned for good, and a graph-wide collapse silently skips it — "unset
    tracks, set ignores", per hop. That makes this the counterpart to the
    graph-tier toggle, not a tidy-up: without a way back, the tier stops being
    able to reassert over anything the user has touched.
    """

    actions: SelectionActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return _selected_nodes_only(ctx)

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        with layout:
            hui.menu_row(
                _FOLLOW_GRAPH_LABEL,
                icon=hui.icon.reset,
                tooltip=_FOLLOW_GRAPH_TOOLTIP,
                on_click=self.actions.clear_selection_detail_overrides,
            )

    def draw_disabled(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        with layout:
            hui.menu_row(_FOLLOW_GRAPH_LABEL, icon=hui.icon.reset, enabled=False)
