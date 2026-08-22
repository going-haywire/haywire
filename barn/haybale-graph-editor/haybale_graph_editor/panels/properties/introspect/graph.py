# barn/haybale-graph-editor/haybale_graph_editor/panels/properties/introspect/graph.py
"""
GraphInfoPanel — read-only facts about the active graph.

Node and edge counts, plus the framework-written metadata (filestem,
created_at, modified_at). Those three live here rather than in the
metadata panel because they have no setter and a settings-bag renderer
draws every field as editable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.core.signals import GraphSaved
from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel, PanelLayout
from haywire.ui.panel.decorator import panel

from ....focuses import GraphFocus
from ....state.edit_state import EditState

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


def _format_stamp(value: str | None) -> str:
    """ISO timestamp -> 'YYYY-MM-DD HH:MM'. Falls back to the raw value."""
    if not value:
        return "—"
    try:
        from datetime import datetime

        return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return str(value)


@panel(
    focus=GraphFocus,
    label="Graph Info",
    icon=hui.icon.graph,
    order=10,
    redraw_on=(GraphSaved,),
)
class GraphInfoPanel(BasePanel):
    """Displays counts and framework-written metadata for the active graph."""

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.data[EditState].active_graph is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        graph = ctx.data[EditState].active_graph
        if graph is None:
            return
        with layout:
            try:
                nodes = graph.list_node_wrappers()
                edges = graph.list_edge_wrappers()
                node_count = len(nodes) if hasattr(nodes, "__len__") else "?"
                edge_count = len(edges) if hasattr(edges, "__len__") else "?"
                # No graph_id fallback: it is a transient uuid and means
                # nothing to a user.
                hui.info_row("File", str(getattr(graph, "filestem", None) or "?"))
                hui.info_row("Nodes", str(node_count))
                hui.info_row("Edges", str(edge_count))
                hui.info_row("Created", _format_stamp(getattr(graph, "created_at", None)))
                hui.info_row("Modified", _format_stamp(getattr(graph, "modified_at", None)))
            except Exception:
                hui.error_label("Error reading graph info")
