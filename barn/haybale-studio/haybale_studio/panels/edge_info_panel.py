# packages/haywire-core/src/haywire/ui/panels/edge_info_panel.py
"""
EdgeInfoPanel — shows source and target information for the selected edge.
"""

from haywire.ui.panel.decorator import panel
from haywire.ui.panel.base import BasePanel, PanelLayout

if False:  # TYPE_CHECKING
    from haywire.ui.context import SessionContext


@panel(
    registry_id='edge_info',
    editor='properties',
    scope='edge',
    label='Edge Info',
    icon='linear_scale',
    order=10,
)
class EdgeInfoPanel(BasePanel):
    """Displays source/target node and port info for the selected edge."""

    @classmethod
    def poll(cls, context: 'SessionContext') -> bool:
        return context.active_edge is not None

    def draw(self, context: 'SessionContext', layout: PanelLayout) -> None:
        edge = context.active_edge
        if edge is None:
            return
        try:
            wrapper = edge.wrapper if hasattr(edge, 'wrapper') else edge
            conn_uuid = getattr(wrapper, 'edge_id', getattr(edge, 'ui_edge_id', '?'))
            source_node = getattr(wrapper, 'source_node_id', '?')
            outlet_pin = getattr(wrapper, 'outlet_port_id', '?')
            sink_node = getattr(wrapper, 'sink_node_id', '?')
            inlet_pin = getattr(wrapper, 'inlet_port_id', '?')
            is_valid = wrapper.is_valid() if callable(getattr(wrapper, 'is_valid', None)) else '?'

            layout.label(f"ID: {conn_uuid}")
            layout.separator()
            layout.label(f"Source: {source_node}")
            layout.label(f"  outlet: {outlet_pin}")
            layout.separator()
            layout.label(f"Target: {sink_node}")
            layout.label(f"  inlet: {inlet_pin}")
            layout.separator()
            layout.label(f"Valid: {is_valid}")
        except Exception:
            layout.label('Error reading edge info')
