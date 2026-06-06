# packages/haywire-core/src/haywire/ui/panels/graph_info_panel.py
"""
GraphInfoPanel — shows node and edge counts for the active graph.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel, PanelLayout
from haywire.ui.panel.decorator import panel

from ..focuses import GraphFocus
from ..state.edit_state import EditState

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


@panel(
    focus=GraphFocus,
    label="Graph Info",
    icon=hui.icon.graph,
    order=10,
)
class GraphInfoPanel(BasePanel):
    """Displays node and edge counts for the active graph."""

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
                edges = graph.list_edge_wrappers
                node_count = len(nodes) if hasattr(nodes, "__len__") else "?"
                edge_count = len(edges) if hasattr(edges, "__len__") else "?"
                graph_name = getattr(graph, "name", None) or getattr(graph, "graph_id", "?")
                hui.info_row("Graph", str(graph_name))
                hui.info_row("Nodes", str(node_count))
                hui.info_row("Edges", str(edge_count))
            except Exception:
                hui.error_label("Error reading graph info")
