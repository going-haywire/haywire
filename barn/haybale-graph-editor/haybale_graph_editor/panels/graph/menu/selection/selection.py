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

Rows group into bands by ``order`` (see ``SelectionMenu``), with a separator
between bands. The macro verbs sit one level down on ``SelectionMacroMenu``;
source, cloning and rebuilding on ``SelectionDevelopMenu``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haybale_graph_editor.panels._gating import (
    is_cloneable_selection,
    is_collapsible_selection,
    is_graph_node,
    is_macro_placement,
    is_modified_instance,
    is_reroute_node,
)
from nicegui import ui

from haywire.core.access import AccessTier
from haywire.core.signals import Copy, Delete
from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel
from haywire.ui.panel.layout import PanelLayout
from haywire.ui.panel.decorator import panel

from haybale_graph_editor.panels.graph.menu.component_rows import component_row, identity_of, key_and_label
from haybale_graph_editor.surfaces import (
    SelectionActions,
    SelectionDetailMenu,
    SelectionDevelopMenu,
    SelectionEditMenu,
    SelectionMacroMenu,
    SelectionMenu,
)
from haybale_graph_editor.state.edit_state import EditState

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
#  -> MacroSelectionMenuPanel
#     -> SelectionMacroMenu
#  -> DevelopSelectionMenuPanel
#     -> SelectionDevelopMenu
#        -> EditSelectionMenuPanel -> SelectionEditMenu
#        -> CloneToLibraryMenuPanel
#        -> RebuildSelectionMenuPanel -> SelectionRebuildMenu
#  -> DeleteSelectionMenuPanel


def _selected_nodes_only(ctx: "SessionContext") -> bool:
    """True when the selection holds at least one NODE.

    Edges have no card, so an edge-only selection must not offer either axis —
    the commands would poll true and then do nothing.
    """
    return bool(ctx.data[EditState].selected_nodes)


@panel(
    surface=SelectionMenu,
    label="Fold",
    description="Fold or unfold every selected node — one row, both directions.",
    icon=hui.icon.node_collapse,
    order=400,
)
class CollapseSelectionMenuPanel(BasePanel):
    """Fold or unfold every selected node — one row, both directions.

    **The row rewrites itself on click rather than closing over its state.**
    It is drawn with ``closes=False``, so the menu stays open after the
    command runs: a handler that captured ``collapsed`` at draw time would
    keep re-sending that same value, and the toggle would work exactly once.
    The current state is asked for on every click
    (``toggle_selection_collapsed`` decides server-side and returns the new
    state), and the label and icon are updated in place from the answer, so
    what the row says stays true while the menu remains open.

    The icon names the action, not the state — it pairs with the label, which
    also says the verb. An icon showing the *current* state beside a label
    saying the *next* one reads as a contradiction.
    """

    actions: SelectionActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        if is_reroute_node(ctx):
            return False
        return _selected_nodes_only(ctx)

    @staticmethod
    def _row_text(collapsed: bool, n_nodes: int) -> str:
        return selection_label("Unfold" if collapsed else "Fold", n_nodes, 0)

    @staticmethod
    def _row_icon(collapsed: bool) -> str:
        return hui.icon.node_expand if collapsed else hui.icon.node_collapse

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        n_nodes = len(ctx.data[EditState].selected_nodes)
        collapsed = self.actions.selection_is_collapsed()

        def _toggle() -> None:
            now_collapsed = self.actions.toggle_selection_collapsed()
            if label_el is not None:
                label_el.set_text(self._row_text(now_collapsed, n_nodes))
            if icon_el is not None:
                icon_el.set_name(self._row_icon(now_collapsed))

        with layout:
            row = hui.menu_row(
                self._row_text(collapsed, n_nodes),
                icon=self._row_icon(collapsed),
                on_click=_toggle,
                closes=False,
            )

        # Reach into the row this panel just built to relabel it after a click.
        # menu_row's shape is (icon?, label) and it always makes both here,
        # since an icon was passed — but read them defensively rather than by
        # index, so a change to that shape degrades to "the row stops
        # relabelling" instead of raising out of a click handler.
        icon_el = next((c for c in row.default_slot.children if isinstance(c, ui.icon)), None)
        label_el = next((c for c in row.default_slot.children if isinstance(c, ui.label)), None)

    def draw_disabled(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        if is_reroute_node(ctx) is False:
            with layout:
                with layout:
                    hui.menu_row("Fold", icon=hui.icon.node_collapse, enabled=False)


@panel(
    surface=SelectionMenu,
    label="Copy Selection",
    description="Copy the selected nodes and edges to the clipboard.",
    icon=hui.icon.copy,
    order=100,
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
                command=Copy,
            )

    def draw_disabled(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        """The static form, greyed — what the row should say with nothing selected."""
        with layout:
            hui.menu_row("Copy", icon=hui.icon.copy, enabled=False, command=Copy)


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
    description="Node errors panel for the unified selection context menu.",
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
    description="Collapse a reroute node back into a direct connection.",
    icon=hui.icon.edge,
    order=230,
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
        return is_reroute_node(ctx)

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


def _single_node(ctx: "SessionContext"):
    """The one selected node's wrapper, or None.

    Skin and theme resolve per node, so a multi-node selection has no single
    answer and this returns None rather than picking one arbitrarily. Reads
    ``active_node`` — canvas.vue's "replace-then-act" makes it the node under
    the cursor — but only once the selection agrees it is alone.
    """
    edit = ctx.data[EditState]
    if len(edit.selected_nodes) != 1 or edit.selected_edges:
        return None
    return edit.active_node


@panel(
    surface=SelectionDevelopMenu,
    hosts=(SelectionEditMenu,),
    label="Edit Source",
    description='The "Edit Source" row — a submenu over the components behind this node.',
    icon=hui.icon.node_source,
    order=10,
)
class EditSelectionMenuPanel(BasePanel):
    """The "Edit Source" row — a submenu over the components behind this node.

    A hosting panel: it draws only the row and the flyout, piping the
    ``SelectionActions`` host one hop further, exactly as
    ``DetailSelectionMenuPanel`` does. The pin menu carries the same row over
    its own subjects, so the gesture reads identically on either target.

    Single-node only: skin and theme resolve per node, and a mixed or
    multi-node selection has no one answer to give.

    The node row always draws for a single node (a wrapper carries its
    registry key by construction), so unlike the pin menu's Edit row this one
    cannot end up hosting an empty body — and a hosting panel that polls true
    over nothing would cost this menu its popup, since a hosting panel is
    excluded from the leaf count (ADR-0029). Copy/Delete draw beside it
    regardless, so the risk is theirs to absorb; the single-node rule is
    still what keeps the row honest.
    """

    actions: SelectionActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return _single_node(ctx) is not None

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        with layout:
            with hui.submenu_row("Edit Source", icon=hui.icon.node_source):
                self.render_surface(SelectionEditMenu, ctx)

    def draw_disabled(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        if _selection_nonempty(ctx):
            with layout:
                hui.menu_row("Edit Source", icon=hui.icon.node_source, enabled=False)


@panel(
    surface=SelectionEditMenu,
    label="Node",
    description="The node class itself, as a row that opens its source.",
    icon=hui.icon.node,
    order=10,
)
class NodeSourceMenuPanel(BasePanel):
    """The node class itself, as a row that opens its source."""

    actions: SelectionActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return _single_node(ctx) is not None

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        wrapper = _single_node(ctx)
        if wrapper is None:
            return
        # A node wrapper carries its registry key directly — it is what the
        # wrapper was built from, so there is no class to re-resolve.
        key = getattr(wrapper, "registry_key", "") or ""
        label = getattr(getattr(wrapper.node, "identity", None), "label", "") or key
        with layout:
            component_row(ctx, label, key, hui.icon.node)


@panel(
    surface=SelectionEditMenu,
    label="Skin",
    description="The skin that drew this node's card, as a row opening its source.",
    icon=hui.icon.skin,
    order=20,
)
class NodeSkinMenuPanel(BasePanel):
    """The skin that drew this node's card, as a row opening its source.

    ``props.skin`` already resolves the graph < node chain, so it holds the
    key actually in effect. It is None when the node defers entirely to the
    registry's default, which ``ui_node`` substitutes at render time — so the
    same fallback is applied here, or the row would vanish on every node that
    never overrode its skin (which is most of them).
    """

    actions: SelectionActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return bool(cls._skin_key(ctx))

    @staticmethod
    def _skin_key(ctx: "SessionContext") -> str:
        wrapper = _single_node(ctx)
        if wrapper is None:
            return ""
        try:
            key = wrapper.node.props.skin
        except Exception:
            return ""
        if key:
            return str(key)
        # Same fallback, reached the same way, as ``UINode._render``: the
        # registry default is what actually draws a node whose prop is unset.
        app = ctx.app
        factory = getattr(app, "skin_factory", None) if app is not None else None
        registry = getattr(factory, "_skin_registry", None) if factory is not None else None
        if registry is None:
            return ""
        return registry.get_default_skin_registry_key() or ""

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        key = self._skin_key(ctx)
        if not key:
            return
        app = ctx.app
        cls_ = app.library_service.lookup_component_class(key) if app is not None else None
        _resolved, label = key_and_label(identity_of(cls_), key)
        with layout:
            component_row(ctx, label or key, key, hui.icon.skin)


@panel(
    surface=SelectionEditMenu,
    label="Theme",
    description="The node theme colouring this card, as a row opening its source.",
    icon=hui.icon.theme,
    order=30,
)
class NodeThemeMenuPanel(BasePanel):
    """The node theme colouring this card, as a row opening its source.

    ``props.node_theme`` resolves the graph < node chain like ``skin`` does,
    but has no registry-default substitute: an empty value means the card
    takes its colours from the workbench theme, and there is no node theme to
    open. The row polls false rather than pointing at something arbitrary.
    """

    actions: SelectionActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return bool(cls._theme_key(ctx))

    @staticmethod
    def _theme_key(ctx: "SessionContext") -> str:
        wrapper = _single_node(ctx)
        if wrapper is None:
            return ""
        try:
            return str(wrapper.node.props.node_theme or "")
        except Exception:
            return ""

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        key = self._theme_key(ctx)
        if not key:
            return
        app = ctx.app
        cls_ = app.library_service.lookup_component_class(key) if app is not None else None
        _resolved, label = key_and_label(identity_of(cls_), key)
        with layout:
            component_row(ctx, label or key, key, hui.icon.theme)


@panel(
    surface=SelectionMenu,
    hosts=(SelectionDetailMenu,),
    label="Detail",
    description='The "Detail" row — a submenu over the density ranks.',
    icon=hui.icon.node_detail,
    order=410,
)
class DetailSelectionMenuPanel(BasePanel):
    """The "Detail" row — a submenu over the density ranks.

    A hosting panel: it draws only the row and the flyout, and pipes the
    ``SelectionActions`` host one hop further to the rows inside.
    """

    actions: SelectionActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        if is_reroute_node(ctx):
            return False
        return _selected_nodes_only(ctx)

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        with layout:
            with hui.submenu_row("Detail", icon=hui.icon.node_detail):
                self.render_surface(SelectionDetailMenu, ctx)

    def draw_disabled(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        if is_reroute_node(ctx) is False:
            with layout:
                hui.menu_row("Detail", icon=hui.icon.node_detail, enabled=False)


@panel(
    surface=SelectionDetailMenu,
    label="Detail Ranks",
    description="One row per node detail rank.",
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


_RESET_DETAIL_LABEL = "Reset Detail"
_RESET_DETAIL_TOOLTIP = "Clear this node's own detail rank so it follows the graph again"


@panel(
    surface=SelectionDetailMenu,
    label=_RESET_DETAIL_LABEL,
    description="Drop each selected node's own detail rank, so it follows the graph's again.",
    icon=hui.icon.reset,
    order=20,
)
class ClearDetailOverridesMenuPanel(BasePanel):
    """Drop each selected node's own detail rank, inside the Detail submenu
    it undoes — beside the ranks it resets, not on the top-level menu.

    Without this a node that has ever been re-ranked by hand is pinned for
    good, and a graph-wide detail change silently skips it — "unset tracks,
    set ignores", per hop. That makes this the counterpart to the graph-tier
    setting, not a tidy-up: without a way back, the tier stops being able to
    reassert over anything the user has touched.

    Collapse is NOT reset here: it is no longer inherited from the graph, so
    there is nothing for a node's own collapse state to fall back to — see
    ``SelectionDetailMenu``.
    """

    actions: SelectionActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return _selected_nodes_only(ctx)

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        with layout:
            hui.menu_row(
                _RESET_DETAIL_LABEL,
                icon=hui.icon.reset,
                tooltip=_RESET_DETAIL_TOOLTIP,
                on_click=self.actions.clear_selection_detail_overrides,
            )

    def draw_disabled(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        with layout:
            hui.menu_row(_RESET_DETAIL_LABEL, icon=hui.icon.reset, enabled=False)


@panel(
    surface=SelectionMenu,
    label="Delete Selection",
    description="Delete every node and edge in the current selection in one undoable step.",
    icon=hui.icon.delete,
    order=600,
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
                command=Delete,
            )

    def draw_disabled(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        """The static form, greyed — what the row should say with nothing selected."""
        with layout:
            hui.menu_row("Delete", icon=hui.icon.delete, enabled=False, command=Delete)


@panel(
    surface=SelectionMenu,
    label="Collapse to Group",
    description="Collapse the selection into one Graph-node standing for a Subgraph.",
    icon=hui.icon.subgraph,
    order=210,
)
class CollapseToGroupMenuPanel(BasePanel):
    """Collapse the selection into one Graph-node standing for a Subgraph.

    Offered whenever two or more nodes are selected. A selection is refused when a
    path that carries values (data, control or callback) leaves it and comes back
    in; visual links don't count. The refusal comes when the command runs, with the
    intervening nodes named — a row that quietly disappeared would leave the user
    with nothing to read.
    """

    actions: SelectionActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return is_collapsible_selection(ctx)

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        n_nodes, _n_edges = _selection_counts(ctx)
        with layout:
            hui.menu_row(
                f"Collapse {n_nodes} Nodes to Group",
                icon=hui.icon.subgraph,
                on_click=self.actions.collapse_to_group,
            )


@panel(
    surface=SelectionMenu,
    label="Enter",
    description="Enter a Group or a macro placement: open its inside as a level of the graph editor.",
    icon=hui.icon.subgraph,
    order=200,
)
class EnterMenuPanel(BasePanel):
    """Enter a Group or a macro placement: open its inside as a level of the graph editor.

    Visible when the right-clicked node is a Graph-node or a macro placement.
    """

    actions: SelectionActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return is_graph_node(ctx) or is_macro_placement(ctx)

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
                "Enter",
                icon=hui.icon.subgraph,
                on_click=lambda: self.actions.enter_group(node_id),
            )


@panel(
    surface=SelectionMenu,
    label="Expand Group",
    description="Expand a Group back into the graph around it.",
    icon=hui.icon.subgraph,
    order=220,
)
class GroupMenuPanel(BasePanel):
    """Expand a Group back into the graph around it.

    Only visible when the right-clicked node is a Graph-node.
    """

    actions: SelectionActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return is_graph_node(ctx)

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
                "Expand Group",
                icon=hui.icon.subgraph,
                on_click=lambda: self.actions.expand_group(node_id),
            )


@panel(
    surface=SelectionMacroMenu,
    label="Save new Macro",
    description="Save a Group as a new macro. Only visible when the right-clicked node is a Graph-node.",
    icon=hui.icon.macro,
    order=50,
)
class SaveNewMacroMenuPanel(BasePanel):
    """Save a Group as a new macro. Only visible when the right-clicked node is a Graph-node."""

    actions: SelectionActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return is_graph_node(ctx)

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        wrapper = ctx.data[EditState].active_node
        if wrapper is None:
            return
        node_id = wrapper.node_id

        with layout:
            hui.menu_row(
                "Save new Macro…",
                icon=hui.icon.macro,
                tooltip="Write this Group to its own file so it can be placed in any graph",
                on_click=lambda: self.actions.promote_to_macro(node_id),
            )


@panel(
    surface=SelectionMacroMenu,
    label="Edit Instance",
    description="Turn one macro placement into a modified instance and enter it.",
    icon=hui.icon.macro,
    order=20,
)
class EditInstanceMenuPanel(BasePanel):
    """Turn one macro placement into a modified instance and enter it.

    Only visible on a placement. The placement becomes a Group of its own that
    remembers the macro it came from; the macro file and every other placement
    of it are unchanged.
    """

    actions: SelectionActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return is_macro_placement(ctx)

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
                "Edit Instance",
                icon=hui.icon.macro,
                tooltip=(
                    "Turn this card into a modified instance and open it. The macro "
                    "file and its other placements are unchanged."
                ),
                on_click=lambda: self.actions.detach_from_macro(node_id),
            )


@panel(
    surface=SelectionMacroMenu,
    label="Modified instance",
    description="Offer to put a modified instance back to its macro, or to cut it loose.",
    icon=hui.icon.macro,
    order=40,
)
class ModifiedInstanceMenuPanel(BasePanel):
    """Offer to put a modified instance back to its macro, or to cut it loose.

    Only visible on a Group that was detached from a macro. Reverting swaps the
    card for a placement of that macro as it stands now, dropping the changes
    made to the instance; that row is greyed when the macro is not installed.
    Forgetting the origin keeps the card as it is and makes it a plain Group.
    """

    actions: SelectionActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return is_modified_instance(ctx)

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        wrapper = ctx.data[EditState].active_node
        if wrapper is None:
            return
        node_id = wrapper.node_id

        from haywire.core.macro.source import macro_template, origin_label

        definition = getattr(wrapper.node, "resolve_definition", lambda: None)()
        origin = getattr(definition, "origin", None)
        template = macro_template(origin.key) if origin is not None else None
        label = origin_label(definition)

        with layout:
            if template is None:
                hui.menu_row(
                    "Revert to Macro",
                    icon=hui.icon.macro,
                    enabled=False,
                    tooltip=f"{label} is not installed.",
                )
            else:
                hui.menu_row(
                    "Revert to Macro",
                    icon=hui.icon.macro,
                    tooltip=(
                        f"Replace this card with a placement of {label}. "
                        "The changes made to this instance are dropped."
                    ),
                    on_click=lambda: self.actions.revert_to_macro(node_id),
                )
            hui.menu_row(
                "Forget Macro Origin",
                icon=hui.icon.macro,
                tooltip=(
                    f"Keep this card as it is, as a plain Group no longer linked to {label}. "
                    "Revert to Macro and Update Macro stop applying to it."
                ),
                on_click=lambda: self.actions.forget_macro_origin(node_id),
            )


@panel(
    surface=SelectionDevelopMenu,
    label="Clone to Library",
    description="Write a copy of this node's class into a library, as a new node to edit.",
    icon=hui.icon.node_clone,
    order=20,
    requires=AccessTier.ADMIN,
)
class CloneToLibraryMenuPanel(BasePanel):
    """Write a copy of this node's class into a library, as a new node to edit.

    Only visible with exactly one node selected whose class may be cloned. The
    copy is a new node class with its own name; this card is unchanged.
    """

    actions: SelectionActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return is_cloneable_selection(ctx)

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
                "Clone to Library…",
                icon=hui.icon.node_clone,
                tooltip="Write a copy of this node's class into a library, as a new node to edit",
                on_click=lambda: self.actions.clone_to_library(node_id),
            )


@panel(
    surface=SelectionMenu,
    hosts=(SelectionMacroMenu,),
    label="Macro",
    description='The "Macro" row — a submenu over the verbs between a card and a macro.',
    icon=hui.icon.macro,
    order=300,
)
class MacroSelectionMenuPanel(BasePanel):
    """The "Macro" row — a submenu over the verbs between a card and a macro.

    Only visible when the right-clicked node is a Group's card or a macro placement.
    """

    actions: SelectionActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return is_graph_node(ctx) or is_macro_placement(ctx)

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        with layout:
            with hui.submenu_row("Macro", icon=hui.icon.macro):
                self.render_surface(SelectionMacroMenu, ctx)


@panel(
    surface=SelectionMenu,
    hosts=(SelectionDevelopMenu,),
    label="Develop",
    description='The "Develop" row — a submenu over the node\'s source, cloning it, and rebuilding.',
    icon=hui.icon.node_source,
    order=500,
)
class DevelopSelectionMenuPanel(BasePanel):
    """The "Develop" row — a submenu over the node's source, cloning it, and rebuilding."""

    actions: SelectionActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return _selection_nonempty(ctx)

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        with layout:
            with hui.submenu_row("Develop", icon=hui.icon.node_source):
                self.render_surface(SelectionDevelopMenu, ctx)
