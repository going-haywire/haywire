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
        
        # Generate unique node ID for CSS scoping
        node_id = f"node-{id(node)}"
        
        # Add CSS for hover effects with node-specific scoping
        ui.add_head_html(f'''
        <style>
        .{node_id} .widget-container {{
            opacity: 0;
            transition: opacity 0.3s ease;
            max-height: 0;
            overflow: hidden;
        }}
        /* Show widgets on hover OR when any widget inside has focus */
        .{node_id}:hover .widget-container,
        .{node_id}:focus-within .widget-container {{
            opacity: 1;
            max-height: 200px;
        }}
        .{node_id} {{
            transition: all 0.2s ease;
        }}
        /* Apply shadow on hover OR focus-within */
        .{node_id}:hover,
        .{node_id}:focus-within {{
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }}
        </style>
        ''')
        
        # Create the main card
        with ui.card().classes(f'w-full min-w-64 max-w-sm node-card {node_id}') as main_card:
            with ui.row().classes('drag-handle'):
                ui.icon('drag_indicator').classes('text-grey-6 text-h6')
                ui.label(node.node_label).classes('text-h6')

            # Main content: inlets and outlets in two columns
            with ui.row().classes('w-full gap-2'):
                # Left column: Inlets
                with ui.column().classes('flex-1 gap-1'):
                    if node.inlets:
                        ui.label('Inputs').classes('font-bold text-sm')
                        for inlet in node.inlets.values():
                            self._render_inlet(inlet, ui_elements, widget_instances)

                # Right column: Outlets
                with ui.column().classes('flex-1 gap-1'):
                    if node.outlets:
                        ui.label('Outputs').classes('font-bold text-sm')
                        for outlet in node.outlets.values():
                            self._render_outlet(outlet)

            # Footer with port counts
            with ui.row().classes('w-full justify-between mt-2'):
                ui.label(f'↓ {len(node.inlets)}').classes('text-caption')
                ui.label(f'↑ {len(node.outlets)}').classes('text-caption')
        
        return UINodeCard(main_card, ui_elements, widget_instances)
    
    def _render_inlet(self, inlet: Inlet, ui_elements: Dict[str, Any], widget_instances: Dict[str, Any]):
        """Render an inlet with its port and optional widget."""
        with ui.row().classes('w-full items-center justify-start gap-1'):
            # only render pins for inlets that are actually involved in flows
            self._render_pin(inlet, direction='left')

            # Pin label
            ui.label(inlet.label).classes('text-xs')

        # Render inlet widget if it has a pin that is not pooled (is_pooled == False)
        if inlet.is_pooled == False:
            self._render_element('inlet', inlet, ui_elements, widget_instances)
    
    def _render_outlet(self, outlet):
        """Render an outlet with its port."""
        with ui.row().classes('w-full items-center justify-end gap-1'):
            # Pin label
            ui.label(outlet.label).classes('text-xs')

            # only render pins for inlets that are actually involved in flows
            self._render_pin(outlet, direction='right')

    
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
            
            # Add widget-container class for hover effects (if element supports classes)
            if hasattr(ui_element, 'classes') and callable(ui_element.classes):
                ui_element.classes('widget-container')
            
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

            render_error_info(creationerror)
    
    def _render_pin(self, pin: ConfigurableElement, direction: str = 'left'):
        """Render an inlet with its port and optional widget."""
        if pin.flow_type == FlowType.CTRL.value:
            # Pin connector
            ui.icon('label', color='blue', size='xs').classes(
                f'text-4xl'
                f'port input-port'
            ).style(
                f'position: absolute; {direction}: -8px; '
                f'cursor: crosshair;'
            ).props(f'data-port-id="{pin.id}"')
        if pin.flow_type == FlowType.CALLBACK.value:
            # Pin connector
            ui.icon('replay_circle_filled', color='red', size='xs').classes(
                f'text-4xl'
                f'port input-port'
            ).style(
                f'position: absolute; {direction}: -8px; '
                f'cursor: crosshair;'
            ).props(f'data-port-id="{pin.id}"')
        elif pin.flow_type == FlowType.DATA.value:
            ui.element('div').classes(
                f'port output-port'
            ).style(
                f'position: absolute; {direction}: -8px; '
                f'width: 15px; height: 15px; '
                f'background: {self._get_port_color(pin.data.type)}; '
                f'border: 2px solid white; '
                f'border-radius: 50%; '
                f'cursor: crosshair;'
            ).props(f'data-port-id="{pin.id}"')
    
    def _get_port_color(self, data_type: str | DataType) -> str:
        """Get the color for a port based on its data type."""
        colors = {
            'float': '#2196f3',
            'int': '#2196f3',
            'string': '#4caf50', 
            'boolean': '#ff9800',
            'array': '#9c27b0',
            'any': '#757575'
        }
        return colors.get(str(data_type), '#757575')

