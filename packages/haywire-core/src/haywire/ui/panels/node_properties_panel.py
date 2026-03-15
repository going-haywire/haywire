# packages/haywire-core/src/haywire/ui/panels/node_properties_panel.py
"""
NodePropertiesPanel — shows basic node identity information.
"""

from haywire.ui.panel.decorator import panel
from haywire.ui.panel.base import BasePanel, PanelLayout

if False:  # TYPE_CHECKING
    from haywire.ui.context import SessionContext


@panel(
    registry_id='node_properties',
    editor='properties',
    context='node',
    label='Node Properties',
    icon='info',
    order=10,
)
class NodePropertiesPanel(BasePanel):
    """Displays basic identity information for the selected node."""

    @classmethod
    def poll(cls, context: 'SessionContext') -> bool:
        return context.active_node is not None

    def draw(self, context: 'SessionContext', layout: PanelLayout) -> None:
        node = context.active_node
        if node is None:
            return
        try:
            label = node.node.identity.label if hasattr(node, 'node') else str(node)
            cls_name = node.node.__class__.__name__ if hasattr(node, 'node') else type(node).__name__
            node_id = getattr(node, 'node_id', str(node))
        except Exception:
            label, cls_name, node_id = '?', '?', '?'
        layout.label(f"Name: {label}")
        layout.label(f"Class: {cls_name}")
        layout.label(f"ID: {node_id}")
