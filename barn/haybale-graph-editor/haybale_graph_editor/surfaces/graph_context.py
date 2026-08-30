"""The canvas right-click menu: its root surface, its two regions, and the
flyout behind the "…".

``GraphContext`` is the root — what ``on_canvas_context`` opens. The panel
sitting on it owns the arrangement and renders the two region surfaces into
the *same* popup; a submenu row drawn on one is a visual sibling of one drawn
on the other, which is exactly why a sibling group belongs to the container
(the popup) rather than to a surface.

This is also where the menu half of the old ``CanvasFocus`` lands. Its
inspector half stays in core as ``CanvasSettings`` (``id="canvas"``), so the
double duty one focus id did — six properties panels and two menu panels
sharing ``id="canvas"``, kept apart only by whether a Protocol was set —
resolves into two surfaces without either changing what a user sees.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from haywire.ui.surface import Surface

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


@runtime_checkable
class GraphActions(Protocol):
    """Verbs available when the user right-clicks the canvas."""

    def create_node_at_click(self, registry_key: str) -> None: ...
    def paste_at_click(self) -> None: ...
    def focus_on_graph(self) -> None: ...

    # ADR 0032. The counterpart to the graph-tier card settings: mirrors are
    # "unset tracks, set ignores", so a graph whose nodes have been folded or
    # re-ranked by hand can never have its tier reassert over them again
    # without this. Graph-wide, unlike the selection-scoped reset on the node
    # menu.
    def clear_node_card_overrides(self) -> int: ...


class GraphContext(Surface):
    """Root of the canvas right-click menu."""

    id = "graph-context"
    provides = GraphActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        from haybale_graph_editor.state.edit_state import EditState

        return ctx.data[EditState].active_graph is not None


class GraphToolBar(Surface):
    """Icon shortcut row along the menu's top edge."""

    id = "graph-toolbar"
    provides = GraphActions


class GraphContextBody(Surface):
    """Prime area below the shortcut row."""

    id = "graph-body"
    provides = GraphActions


class GraphMoreActions(Surface):
    """Secondary commands behind the "…" flyout."""

    id = "graph-more"
    provides = GraphActions
