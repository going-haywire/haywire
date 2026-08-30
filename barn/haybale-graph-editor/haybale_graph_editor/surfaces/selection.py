"""The selection right-click menu and its "Rebuild" submenu.

The single command menu after node/selection unification: every right-click
command acts on the whole selection (``EditState.selected_nodes`` /
``selected_edges``). It is also what the floating toolbar's ⋯ hosts, so the
batch ops live in one place and no panel is duplicated between the two.

``SelectionRebuildMenu`` is the submenu behind the "Rebuild" row: the three
re-run-the-selection commands (redraw / revalidate / reset) are one family and
the menu says so, rather than spending three of its top-level rows on them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from haywire.ui.surface import Surface

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


@runtime_checkable
class SelectionActions(Protocol):
    """Verbs available on a selection (one element or many)."""

    def copy_selection(self) -> None: ...
    def paste_at_click(self) -> None: ...
    def delete_selection(self) -> None: ...
    def redraw_selection(self) -> None: ...
    def revalidate_selection(self) -> None: ...
    def reset_selection(self) -> None: ...
    def dissolve_reroute(self, node_id: str) -> None: ...

    # ADR 0032 card axes, applied across the selection. Right-clicking an
    # unselected node replaces the selection with it first (canvas.vue's
    # "replace-then-act"), so these reach exactly the node under the cursor
    # when nothing else is selected, and the whole set when something is.
    def set_selection_collapsed(self, collapsed: bool) -> None: ...
    def selection_is_collapsed(self) -> bool: ...
    def toggle_selection_collapsed(self) -> bool: ...
    def set_selection_detail(self, detail: str) -> None: ...
    def clear_selection_detail_overrides(self) -> None: ...


class SelectionMenu(Surface):
    """The selection right-click menu."""

    id = "selection"
    provides = SelectionActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        from haybale_graph_editor.state.edit_state import EditState

        edit = ctx.data[EditState]
        return bool(edit.selected_nodes) or bool(edit.selected_edges)


class SelectionRebuildMenu(Surface):
    """The "Rebuild" submenu of ``SelectionMenu`` — redraw / revalidate / reset.

    Declares no ``poll``: the hosting ``RebuildSelectionMenuPanel`` already
    polls the selection, and its panels each render their own greyed form
    when nothing is selected, exactly as they did while sitting flat on
    ``SelectionMenu``. A surface-level gate here would be a second copy of
    that predicate and would swallow the greyed rows instead.
    """

    id = "selection-rebuild"
    provides = SelectionActions


class SelectionDetailMenu(Surface):
    """The "Detail" submenu of ``SelectionMenu`` — the ADR-0032 density ranks.

    One row per ``NodeDetail`` rank plus a row that clears the per-node
    override so the node tracks its graph again. Collapse is NOT here: it is a
    toggle, not a choice among ranks, so it earns its own top-level row.

    Declares no ``poll`` for the same reason ``SelectionRebuildMenu`` does not
    — the hosting panel already gates on the selection, and a second copy of
    that predicate would swallow the greyed rows.
    """

    id = "selection-detail"
    provides = SelectionActions
