"""
Updated NiceGUI Node Renderer using the Widget Registry System

This replaces the hardcoded widget methods in the original NiceGUINodeRenderer
with a registry-based approach that supports the modular library system.
"""

from typing import Any, Optional
from nicegui import ui
from haywire.core.data.enums import CouplingType
from haywire.core.registry.registry import WidgetRegistry
from haywire.core.data.fields import DataField
from haywire.core.node.node import NodeData
from haywire.core.data.enums import FlowType, DataType

class ModularNiceGUINodeRenderer:
    """Renders Haywire nodes using the widget registry system"""
    
    def __init__(self, node: NodeData, widget_registry: WidgetRegistry):
        """Initialize with a node and widget registry"""
        self.node = node
        self.widget_registry = widget_registry
        self.ui_elements = {}
        self.widget_instances = {}
        # Generate unique node ID for CSS scoping
        self.node_id = f"node-{id(self.node)}"
    
    def render_node(self, title: str = "Node"):
        """Render complete node UI using registry-based widgets"""
        
        # Add CSS for hover effects with node-specific scoping
        ui.add_head_html(f'''
        <style>
        .{self.node_id} .widget-container {{
            opacity: 0;
            transition: opacity 0.3s ease;
            max-height: 0;
            overflow: hidden;
        }}
        /* Show widgets on hover OR when any widget inside has focus */
        .{self.node_id}:hover .widget-container,
        .{self.node_id}:focus-within .widget-container {{
            opacity: 1;
            max-height: 200px;
        }}
        .{self.node_id} {{
            transition: all 0.2s ease;
        }}
        /* Apply shadow on hover OR focus-within */
        .{self.node_id}:hover,
        .{self.node_id}:focus-within {{
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }}
        </style>
        ''')
        
        with ui.card().classes(f'w-full min-w-64 max-w-sm node-card {self.node_id}'):
            ui.label(title).classes('text-h6 w-full')

            # Render configs first (if any)
            if self.node.configs:
                ui.label('Configuration').classes('font-bold text-sm mt-2 w-full')
                for config in self.node.configs.values():
                    ui.label(config.label).classes('text-xs')
                    with ui.element('div').classes('widget-container'):
                        self._render_element('config', config)

            # Main content: inlets and outlets in two columns
            with ui.row().classes('w-full gap-2'):
                # Left column: Inlets
                with ui.column().classes('flex-1 gap-1'):
                    if self.node.inlets:
                        ui.label('Inputs').classes('font-bold text-sm')
                        for inlet in self.node.inlets.values():
                            with ui.row().classes('w-full items-center justify-start gap-1'):
                                # Pin connector
                                ui.element('div').classes(
                                    f'port input-port'
                                ).style(
                                    f'position: absolute; left: -6px; '
                                    f'width: 12px; height: 12px; '
                                    f'background: {self._get_port_color(inlet.data.type)}; '
                                    f'border: 2px solid white; '
                                    f'border-radius: 50%; '
                                    f'cursor: crosshair;'
                                ).props(f'data-port-id="{inlet.id}"')
                                
                                # Pin label
                                ui.label(inlet.label).classes('text-xs')

                            # Render inlet widget if it has UI (coupling_type != NONE)
                            if inlet.coupling_type != CouplingType.NONE:
                                self._render_element('inlet', inlet).classes('widget-container')

                # Right column: Outlets
                with ui.column().classes('flex-1 gap-1'):
                    if self.node.outlets:
                        ui.label('Outputs').classes('font-bold text-sm')
                        for outlet in self.node.outlets.values():
                            with ui.row().classes('w-full items-center justify-end gap-1'):
                                # Pin label
                                ui.label(outlet.label).classes('text-xs')
                                
                                # Pin connector
                                ui.element('div').classes(
                                    f'port output-port'
                                ).style(
                                    f'position: absolute; right: -6px; '
                                    f'width: 12px; height: 12px; '
                                    f'background: {self._get_port_color(outlet.data.type)}; '
                                    f'border: 2px solid white; '
                                    f'border-radius: 50%; '
                                    f'cursor: crosshair;'
                                ).props(f'data-port-id="{outlet.id}"')

            # Show inlet/outlet status
            with ui.row().classes('w-full justify-between mt-2'):
                ui.label(f'↓ {len(self.node.inlets)}').classes('text-caption')
                ui.label(f'↑ {len(self.node.outlets)}').classes('text-caption')

    def _get_port_color(self, data_type: str | DataType) -> str:
        """Get the color for a port based on its data type"""
        colors = {
            'float': '#2196f3',
            'int': '#2196f3',
            'string': '#4caf50', 
            'boolean': '#ff9800',
            'array': '#9c27b0',
            'any': '#757575'
        }
        return colors.get(str(data_type), '#757575')
     
    def _render_element(self, element_type: str, element):
        """Render a single config or property element using widget registry"""
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
            self.ui_elements[element.id] = ui_element
            self.widget_instances[element.id] = widget_instance
            
            return ui_element
            
        except Exception as e:
            # Fallback to error display if widget creation fails
            error_widget = self._render_error_widget(element, str(e))
            return error_widget

    def _render_error_widget(self, element, error_message: str):
        """Render an error widget when widget creation fails"""
        with ui.column().classes('w-full p-2 border border-red-500 bg-red-50') as error_container:
            ui.icon('error', color='red').classes('text-lg')
            ui.label(f"Widget Error: {error_message}").classes('text-red-700 text-sm font-bold')
            ui.label(f"Element: {element.id}").classes('text-red-600 text-xs')
            ui.label(f"Requested widget: {getattr(element, 'widget', 'None')}").classes('text-red-600 text-xs')
        return error_container
    
    def get_widget_instance(self, element_id: str):
        """Get a widget instance by element ID"""
        return self.widget_instances.get(element_id)
    
    def get_ui_element(self, element_id: str):
        """Get a UI element by element ID"""
        return self.ui_elements.get(element_id)
    
    def update_element_value(self, element_id: str, new_value: Any):
        """Update an element's value through its widget"""
        widget_instance = self.widget_instances.get(element_id)
        if widget_instance:
            widget_instance.update_value(new_value)


def create_library_aware_renderer(node: NodeData, 
                                 widget_registry: Optional[WidgetRegistry] = None) -> ModularNiceGUINodeRenderer:
    """
    Factory function to create a renderer with library system support.
    
    If no widget_registry is provided, this would typically load it from
    the global library system (not implemented in this demo).
    """
    if widget_registry is None:
        # In a full implementation, this would get the global widget registry
        # For now, we'll create a minimal one
        from haywire.libraries.core.widgets import register_core_widgets
        widget_registry = WidgetRegistry()
        register_core_widgets(widget_registry)
    
    return ModularNiceGUINodeRenderer(node, widget_registry)


# Backward compatibility alias
NiceGUINodeRenderer = ModularNiceGUINodeRenderer
