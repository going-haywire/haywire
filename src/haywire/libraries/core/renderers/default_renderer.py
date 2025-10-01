"""
Default NodeRenderer

This renderer provides the standard node appearance and functionality
"""

from typing import Dict, Any
from nicegui import ui
from nicegui.element import Element
from haywire.core.node.node import BaseNode, NodeErrorInfo
from haywire.core.data.enums import DataType, FlowType
from haywire.core.ui.renderer import BaseNodeRenderer
from haywire.core.node.elements import Inlet, Outlet, ConfigurableElement
from haywire.core.ui.base import UINodeCard
from haywire.ui.utils import generate_pin_uuid
from haywire.ui.utils import render_error_info

class DefaultNodeRenderer(BaseNodeRenderer):
    """
    Default renderer that provides the standard node appearance.
    
    This is based on the existing ModularNiceGUINodeRenderer design
    and serves as the fallback renderer when no specific renderer is requested.
    """
    
    def render(self, node: BaseNode) -> UINodeCard:
        """
        Render a node using the default design.
        
        Args:
            node: The HaywireNode to render
            
        Returns:
            UINodeCard containing the rendered UI and widget instances
        """
        # Storage for UI elements and widget instances
        ui_elements: Dict[str, Any] = {}
        widget_instances: Dict[str, Any] = {}
        
        # Create the main card
        with ui.card().classes(f'w-full min-w-64 max-w-sm node-card zoom-pan-lod0') as main_card:
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
    
    def _render_inlet(self, inlet: Inlet, ui_elements: Dict[str, Any], widget_instances: Dict[str, Any], node: BaseNode):
        """Render an inlet with its port and optional widget."""
        with ui.row().classes('w-full items-center justify-start gap-1'):
            # only render pins for inlets that are actually involved in flows
            self._render_pin(inlet, direction='left', node=node)

            # Pin label
            ui.label(inlet.label).classes('text-xs zoom-pan-lod2')

        # Render inlet widget if it has a pin that is not pooled (is_pooled == False)
        if inlet.is_pooled == False:
            widget = self._render_element('inlet', inlet, ui_elements, widget_instances)
            # Add widget-container class for fold/unfold functionality (if element supports classes)
            if hasattr(widget, 'classes') and callable(widget.classes):
                widget.classes('widget-container zoom-pan-lod2')

    
    def _render_outlet(self, outlet, node: BaseNode):
        """Render an outlet with its port."""
        with ui.row().classes('w-full items-center justify-end gap-1'):
            # Pin label
            ui.label(outlet.label).classes('text-xs')

            # only render pins for inlets that are actually involved in flows
            self._render_pin(outlet, direction='right', node=node)

    
    def _render_element(self, element_type: str, element, ui_elements: Dict[str, Any], widget_instances: Dict[str, Any]) -> Element:
        """Render a single element using widget registry"""
        if not element.data or element.widget == 'None':
            return
        
        # Get widget name and properties
        widget_name = element.widget
        
        try:
            # Get widget class from registry (with fallback strategy depending on data type)
            widget_class = self.widget_registry.get_widget_class(widget_name, element.data)
            
            # Create widget instance
            widget_instance = widget_class(element)
            
            # Render the widget
            ui_element = widget_instance.render()
                        
            # Store references
            ui_elements[element.id] = ui_element
            widget_instances[element.id] = widget_instance
            
            return ui_element
            
        except Exception as e:
            # Fallback to error display if widget creation fails
            creationerror = NodeErrorInfo(
                error='Widget Creation Error',
                error_message=str(e)
            )
            creationerror.add_note(f"Element: {element.id}")
            creationerror.add_note(f"Requested widget: {getattr(element, 'widget', 'None')}")

            return render_error_info(creationerror)
    
    def _render_pin(self, pin: ConfigurableElement, direction: str = 'left', node: BaseNode = None):
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
        
        if pin.flow_type == FlowType.CTRL.value:
            # Pin connector
            ui.icon('label', color='#0000ff', size='xs').classes(
                'text-4xl port input-port connection-pin zoom-pan-lod0'
            ).style(
                f'position: absolute; {direction}: -20px; '
                f'cursor: crosshair;'
            ).props(
                f'{common_props} '
                f'data-pin-color="#0000ff"'
            )
        elif pin.flow_type == FlowType.CALLBACK.value:
            # Pin connector
            ui.icon('replay_circle_filled', color='red', size='xs').classes(
                'text-4xl port input-port connection-pin zoom-pan-lod0'
            ).style(
                f'position: absolute; {direction}: -20px; '
                f'cursor: crosshair;'
            ).props(
                f'{common_props} '
                f'data-pin-color="#ff0000"'
            )
        elif pin.flow_type == FlowType.DATA.value:
            pin_color = self._get_port_color(pin.data.type)
            ui.element('div').classes(
                'port output-port connection-pin zoom-pan-lod0'
            ).style(
                f'position: absolute; {direction}: -20px; '
                f'width: 15px; height: 15px; '
                f'background: {pin_color}; '
                f'border: 2px solid white; '
                f'border-radius: 50%; '
                f'cursor: crosshair;'
            ).props(
                f'{common_props} '
                f'data-pin-data-type="{pin.data.type}" '
                f'data-pin-color="{pin_color}"'
            )

    
    def _get_port_color(self, data_type: str | DataType) -> str:
        """Get the color for a port based on its data type."""
        colors = {
            'float': "#50b0ff",
            'int': "#f7b0ff",
            'string': '#4caf50', 
            'boolean': '#ff9800',
            'array': '#9c27b0',
            'any': "#BABABA"
        }
        return colors.get(str(data_type), '#757575')

