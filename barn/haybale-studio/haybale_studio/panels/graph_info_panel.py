# packages/haywire-core/src/haywire/ui/panels/graph_info_panel.py
"""
GraphInfoPanel — shows node and edge counts for the active graph.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.ui import elements as hui
from haywire.ui.panel import Panel, PanelLayout
from haywire.ui.panel.decorator import panel

from haybale_studio.focuses import GraphFocus
from haybale_studio.editors.properties_editor_actions import PropertiesEditorActions
from haybale_studio.state.edit_state import EditState

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext


@panel(
    action=PropertiesEditorActions,
    focus=GraphFocus,
    label="Graph Info",
    icon=hui.icon.graph,
    order=10,
)
class GraphInfoPanel(Panel):
    """Displays node and edge counts for the active graph."""

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.data[EditState].active_graph.value is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: PropertiesEditorActions,
    ) -> None:
        graph = ctx.data[EditState].active_graph.value
        if graph is None:
            return
        try:
            nodes = graph.list_node_wrappers()
            edges = graph.list_edge_wrappers
            node_count = len(nodes) if hasattr(nodes, "__len__") else "?"
            edge_count = len(edges) if hasattr(edges, "__len__") else "?"
            layout.label(f"Nodes: {node_count}")
            layout.label(f"Edges: {edge_count}")
            graph_name = getattr(graph, "name", None) or getattr(graph, "graph_id", "?")
            layout.label(f"Graph: {graph_name}")
        except Exception:
            layout.label("Error reading graph info")
