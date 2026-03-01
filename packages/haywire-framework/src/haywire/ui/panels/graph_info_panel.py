# packages/haywire-framework/src/haywire/ui/panels/graph_info_panel.py
"""
GraphInfoPanel — shows node and edge counts for the active graph.
"""

from haywire.ui.panel.decorator import panel
from haywire.ui.panel.base import BasePanel, PanelLayout

if False:  # TYPE_CHECKING
    from haywire.ui.context import SessionContext


@panel(
    registry_id='graph_info',
    editor='properties',
    context='graph',
    label='Graph Info',
    icon='account_tree',
    order=10,
)
class GraphInfoPanel(BasePanel):
    """Displays node and edge counts for the active graph."""

    @classmethod
    def poll(cls, context: 'SessionContext') -> bool:
        return context.active_graph is not None

    def draw(self, context: 'SessionContext', layout: PanelLayout) -> None:
        graph = context.active_graph
        if graph is None:
            return
        try:
            nodes = getattr(graph, 'nodes', {})
            edges = getattr(graph, 'edges', {})
            node_count = len(nodes) if hasattr(nodes, '__len__') else '?'
            edge_count = len(edges) if hasattr(edges, '__len__') else '?'
            layout.label(f"Nodes: {node_count}")
            layout.label(f"Edges: {edge_count}")
            graph_name = getattr(graph, 'name', None) or getattr(graph, 'graph_id', '?')
            layout.label(f"Graph: {graph_name}")
        except Exception:
            layout.label('Error reading graph info')
