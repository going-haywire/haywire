"""The floating selection toolbar.

There is no overflow surface: the ⋯ is an ordinary hosting panel that renders
``SelectionMenu`` into a flyout, so the toolbar shows the same panel classes
the right-click menu yields rather than a duplicated set.

``provides`` is ``SelectionActions``, and ``SelectionToolbarProvider``
satisfies all seven verbs — five by delegating to the context-menu provider
constructed alongside it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.ui.surface import Surface

from .selection import SelectionActions

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


class SelectionToolbar(Surface):
    """The floating toolbar above the canvas selection bounding box.

    Declares no ``presentation``: it is a root surface, but not a properties
    tab, so the strip does not list it.
    """

    id = "toolbar"
    order = 91  # just after SelectionMenu's historical 90
    provides = SelectionActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        from haybale_graph_editor.state.edit_state import EditState

        edit = ctx.data[EditState]
        return bool(edit.selected_nodes) or bool(edit.selected_edges)
