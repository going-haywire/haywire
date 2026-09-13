"""The Edge split: an inspector tab and a right-click menu, two surfaces.

``EdgeFocus`` did double duty — four properties panels and five menu panels
on one id, kept apart only by whether a Protocol was set. Dropping that fork
merges them, so the Edge properties tab would grow a "Delete Connection" row
and the edge right-click menu would grow EdgePath.

``EdgeInspector`` keeps ``id="edge"`` and the presentation, so DOM attributes
and docs pointing at ``edge`` are unchanged; the *menu* takes the new id.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from haywire.ui.surface import Presentation, Surface

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


@runtime_checkable
class EdgeActions(Protocol):
    """Verbs available when the user right-clicks an edge."""

    def delete_edge(self, edge_id: str) -> None: ...
    def reconnect_active_edge(self) -> None: ...
    def split_edge_with_reroute(self, edge_id: str) -> None: ...
    def set_edge_lazy(self, edge_id: str, lazy: bool) -> None: ...
    def edge_is_lazy(self, edge_id: str) -> bool: ...
    def toggle_edge_lazy(self, edge_id: str) -> bool: ...


class EdgeInspector(Surface):
    """Properties tab for the active edge. Reads state; needs no host verbs."""

    id = "edge"
    order = 70
    presentation = Presentation(label="Edge", icon="cable")

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        from haybale_graph_editor.state.edit_state import EditState

        return ctx.data[EditState].active_edge is not None


class EdgeMenu(Surface):
    """The edge right-click menu."""

    id = "edge-menu"
    provides = EdgeActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        from haybale_graph_editor.state.edit_state import EditState

        return ctx.data[EditState].active_edge is not None


class EdgeEditMenu(Surface):
    """The "Edit…" submenu of ``EdgeMenu`` — the adapters behind this edge.

    One row per adapter in the edge's chain, each opening that adapter's
    source. Mirrors ``SelectionEditMenu``/``PinEditMenu``: same gesture,
    different subject.

    Declares no ``poll`` for the same reason those two don't — the hosting
    panel already gates on the active edge, and a second copy of that
    predicate would swallow the greyed rows.
    """

    id = "edge-edit"
    provides = EdgeActions
