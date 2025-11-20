"""
Default NodeRenderer

This renderer provides the standard node appearance and functionality
"""

from typing import Dict, Any
from nicegui import ui
from nicegui.element import Element

from haywire.core.node.base_node import BaseNode
from haywire.core.data.enums import FlowType
from haywire.core.ui.base_renderer import BaseNodeRenderer
from haywire.core.types.ports import PortInlet, PortOutlet, DataPort
from haywire.core.ui.base import UINodeCard
from haywire.core.ui.base_widget import BaseWidget
from haywire.ui.themes.colors import Theme_UI_Color
from haywire.ui.utils import generate_pin_uuid
from haywire.ui.utils import render_error_info
from haywire.core.ui.base_renderer import renderer
from haywire.ui.themes import ThemePalette

@renderer(
    description="Default renderer that provides the standard node appearance", 
    is_default=True)
class DefaultNodeRenderer(BaseNodeRenderer):
    """
    Default renderer that provides the standard node appearance.
    
    This is based on the existing ModularNiceGUINodeRenderer design
    and serves as the fallback renderer when no specific renderer is requested.
    """
    
    def _render(self, node: BaseNode) -> UINodeCard:
        """
        Render a node using the default design.
        
        Args:
            node: The HaywireNode to render
            
        Returns:
            UINodeCard containing the rendered UI and widget instances
        """
        # Storage for UI elements and widget instances
        ui_elements: Dict[str, Any] = {}
        widget_instances: Dict[str, BaseWidget] = {}
        
        # Create the main card
        node_bg = ThemePalette.ui(Theme_UI_Color.NODE_BACKGROUND, 'rgba(255, 255, 255, 0.3)')
        with ui.card().classes(
                f'w-full min-w-64 max-w-sm node-card zoom-pan-lod0'
            ).style(
                f'background-color: {node_bg}; backdrop-filter: blur(10px);'
            ) as main_card:
            with ui.row().classes('drag-handle'):
                ui.label(node.identity.label).classes('text-h6')

            # Main content: inlets and outlets in two columns
            with ui.row().classes('w-full gap-2'):
                # Left column: Inlets
                with ui.column().classes('flex-1 gap-1'):
                    if node.inlets:
                        ui.label('Inputs').classes('font-bold text-sm')
                        for inlet in node.inlets.values():
                            self._render_inlet(inlet, ui_elements, widget_instances, node)

                # Right column: Outlets
                with ui.column().classes('flex-1 gap-1'):
                    if node.outlets:
                        ui.label('Outputs').classes('font-bold text-sm')
                        for outlet in node.outlets.values():
                            self._render_outlet(outlet, node)

            # Footer with port counts
            with ui.row().classes('w-full justify-between mt-2 zoom-pan-lod1'):
                ui.label(f'↓ {len(node.inlets)}').classes('text-caption')
                ui.label(f'↑ {len(node.outlets)}').classes('text-caption')
        
        return UINodeCard(main_card, ui_elements, widget_instances)
    
    def _render_inlet(self, inlet: PortInlet, ui_elements: Dict[str, Any], widget_instances: Dict[str, BaseWidget], node: BaseNode):
        """Render an inlet with its port and optional widget."""
        with ui.row().classes('w-full items-center justify-start gap-1'):
            # only render pins for inlets that are actually involved in flows
            self._render_pin(inlet, direction='left', node=node)

            # Pin label
            ui.label(inlet.label).classes('text-xs zoom-pan-lod2')

        # Render inlet widget if it has a pin that is not pooled (is_pooled == False)
        if inlet.is_pooled == False:
            if inlet.widget:
                # Widget rendering adds UI element to current context automatically
                widget = self._render_factory.render_widget(inlet, node.node_id)
                if widget:
                    widget_instances[inlet.id] = widget

    
    def _render_outlet(self, outlet, node: BaseNode):
        """Render an outlet with its port."""
        with ui.row().classes('w-full items-center justify-end gap-1'):
            # Pin label
            ui.label(outlet.label).classes('text-xs')

            # only render pins for inlets that are actually involved in flows
            self._render_pin(outlet, direction='right', node=node)
    
    def _render_pin(self, pin: DataPort, direction: str = 'left', node: BaseNode = None):
        """Render a pin with connection system compatibility."""
        # Create unique pin ID and determine port type for connection system
        pin_direction = 'inlet' if pin.is_inlet() else 'outlet'
        pin_uuid = generate_pin_uuid(pin_direction, node.node_id, pin.id)
        
        # Calculate 2D direction vector components based on pin type
        if pin.is_inlet():
            # Inlets point left (negative X)
            dir_x, dir_y = "-1", "0"
        else:
            # Outlets point right (positive X)
            dir_x, dir_y = "1", "0"
        
        common_props = (
            f'id="{pin_uuid}" '
            f'data-node-id="{node.node_id}" '
            f'data-pin-id="{pin.id}" '
            f'data-pin-flow-type="{pin.flow_type}" '
            f'data-pin-dir="{pin_direction}" '
            f'data-pin-dir-x="{dir_x}" '
            f'data-pin-dir-y="{dir_y}"'
        )
        
        if pin.flow_type == FlowType.CTRL:
            # Get control flow color from theme
            ctrl_color = ThemePalette.flow_type(FlowType.CTRL)
            # Pin connector
            ui.icon('label', color=ctrl_color, size='xs').classes(
                'text-4xl port input-port connection-pin zoom-pan-lod0'
            ).style(
                f'position: absolute; {direction}: -20px; '
                f'cursor: crosshair;'
            ).props(
                f'{common_props} '
                f'data-pin-color="{ctrl_color}"'
            )
        elif pin.flow_type == FlowType.CALLBACK:
            # Get callback flow color from theme
            callback_color = ThemePalette.flow_type(FlowType.CALLBACK)
            # Pin connector
            ui.icon('replay_circle_filled', color=callback_color, size='xs').classes(
                'text-4xl port input-port connection-pin zoom-pan-lod0'
            ).style(
                f'position: absolute; {direction}: -20px; '
                f'cursor: crosshair;'
            ).props(
                f'{common_props} '
                f'data-pin-color="{callback_color}"'
            )
        elif pin.flow_type == FlowType.DATA:
            pin_color = ThemePalette.data_type(pin.cls, pin.color)
            port_border = ThemePalette.ui(Theme_UI_Color.PORT_BORDER, 'white')
            ui.element('div').classes(
                'port output-port connection-pin zoom-pan-lod0'
            ).style(
                f'position: absolute; {direction}: -20px; '
                f'width: 15px; height: 15px; '
                f'background: {pin_color}; '
                f'border: 2px solid {port_border}; '
                f'border-radius: 50%; '
                f'cursor: crosshair;'
            ).props(
                f'{common_props} '
                f'data-pin-data-type="{pin.data.type}" '
                f'data-pin-color="{pin_color}"'
            )
