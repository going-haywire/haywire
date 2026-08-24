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


class NodeAppearance(Surface):
    """The Appearance dropdown, hanging *below* the selection toolbar.

    A content surface, not a command menu: its panels edit the active node's
    own settings bag, so it declares no ``provides`` — there is no verb for a
    host to implement, and a member-less Protocol would match everything
    anyway (ADR-0029).

    Gating lives on the hosting ``AppearanceToolbarPanel``, which needs an
    active *node* (an edges-only selection has none). Restating that here
    would be a second copy of the same predicate.
    """

    id = "node-appearance"


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
