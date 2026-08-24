"""The selection right-click menu.

The single command menu after node/selection unification: every right-click
command acts on the whole selection (``EditState.selected_nodes`` /
``selected_edges``). It is also what the floating toolbar's ⋯ hosts, so the
batch ops live in one place and no panel is duplicated between the two.
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


class SelectionMenu(Surface):
    """The selection right-click menu."""

    id = "selection"
    provides = SelectionActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        from haybale_graph_editor.state.edit_state import EditState

        edit = ctx.data[EditState]
        return bool(edit.selected_nodes) or bool(edit.selected_edges)
