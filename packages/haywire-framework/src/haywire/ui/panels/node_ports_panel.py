# packages/haywire-framework/src/haywire/ui/panels/node_ports_panel.py
"""
NodePortsPanel — lists inlet, outlet, and config ports on the selected node.
"""

from haywire.ui.panel.decorator import panel
from haywire.ui.panel.base import BasePanel, PanelLayout

if False:  # TYPE_CHECKING
    from haywire.ui.context import SessionContext


@panel(
    registry_id='node_ports',
    editor='properties',
    context='node',
    label='Ports',
    icon='device_hub',
    order=20,
)
class NodePortsPanel(BasePanel):
    """Displays the inlet, outlet, and config ports of the selected node."""

    @classmethod
    def poll(cls, context: 'SessionContext') -> bool:
        return context.active_node is not None

    def draw(self, context: 'SessionContext', layout: PanelLayout) -> None:
        node = context.active_node
        if node is None:
            return
        try:
            hw_node = node.node if hasattr(node, 'node') else None
            if hw_node is None:
                layout.label('No port data available')
                return

            inlets = list(getattr(hw_node, 'inlets', {}).values())
            outlets = list(getattr(hw_node, 'outlets', {}).values())
            configs = [
                p for p in getattr(hw_node, 'ports', {}).values()
                if hasattr(p, 'flow_type') and str(getattr(p.flow_type, 'name', '')) == 'NONE'
            ]

            layout.label(f"Inlets ({len(inlets)})")
            for port in inlets:
                port_id = getattr(port, 'port_id', '?')
                port_type = getattr(port, 'data_type', None)
                type_name = port_type.__class__.__name__ if port_type else '?'
                layout.label(f"  • {port_id}: {type_name}")

            layout.separator()
            layout.label(f"Outlets ({len(outlets)})")
            for port in outlets:
                port_id = getattr(port, 'port_id', '?')
                port_type = getattr(port, 'data_type', None)
                type_name = port_type.__class__.__name__ if port_type else '?'
                layout.label(f"  • {port_id}: {type_name}")

            if configs:
                layout.separator()
                layout.label(f"Config ({len(configs)})")
                for port in configs:
                    port_id = getattr(port, 'port_id', '?')
                    layout.label(f"  • {port_id}")

        except Exception:
            layout.label('Error reading ports')
