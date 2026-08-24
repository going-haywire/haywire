"""Inspector surface for the active graph."""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.ui.surface import Presentation, Surface

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


class GraphInspector(Surface):
    """Properties tab describing the active graph."""

    id = "graph"
    order = 50
    presentation = Presentation(label="Graph", icon="polyline")

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        from haybale_graph_editor.state.edit_state import EditState

        return ctx.data[EditState].active_graph is not None
