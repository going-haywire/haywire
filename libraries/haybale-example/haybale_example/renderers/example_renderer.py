
from typing import Any, Dict
from nicegui import ui
from nicegui.element import Element
from haywire.core.node.dataclasses import NodeErrorInfo
from haywire.core.ui.base_renderer import BaseNodeRenderer
from haywire.core.node.base_node import BaseNode
from haywire.core.ui.base import UINodeCard 
from haywire.core.ui.base_renderer import renderer
from haywire.ui.utils import render_error_info

@renderer(description="Custom renderer for nodes with special styling")
class ExampleNodeRenderer(BaseNodeRenderer):
    """Custom renderer for nodes with special styling."""

    def _render(self, node: BaseNode) -> UINodeCard:
        """Render a node with custom styling."""
        ui_elements = {}
        widget_instances = {}
        
        node_id = f"example-node-{id(node)}"
        
        # Custom math-themed CSS
        ui.add_head_html(f'''
        <style>
        .{node_id} {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 16px;
            border: 3px solid #4f46e5;
        }}
        .{node_id} .text-h6 {{
            color: #fbbf24;
            font-weight: bold;
        }}
        .{node_id} .widget-container {{
            opacity: 0;
            transition: all 0.4s ease;
            transform: scale(0.95);
        }}
        .{node_id}:hover .widget-container,
        .{node_id}:focus-within .widget-container {{
            opacity: 1;
            transform: scale(1);
        }}
        </style>
        ''')
        
        with ui.card().classes(f'w-full min-w-64 max-w-sm math-node-card {node_id}') as main_card:
            # Math-themed header
            with ui.row().classes('w-full items-center gap-2'):
                ui.icon('calculate', color='yellow').classes('text-lg')
                ui.label("Math Node").classes('text-h6 flex-1')
                        
            # Render inlets and outlets
            with ui.row().classes('w-full gap-2'):
                # Inlets
                with ui.column().classes('flex-1 gap-1'):
                    if node.inlets:
                        ui.label('Inputs').classes('font-bold text-sm')
                        for inlet in node.inlets.values():
                            with ui.row().classes('w-full items-center gap-1'):
                                ui.label(inlet.label).classes('text-xs')
                                if inlet.is_pooled == False:
                                    self.render_element(inlet, ui_elements, widget_instances)
                
                # Outlets
                with ui.column().classes('flex-1 gap-1'):
                    if node.outlets:
                        ui.label('Outputs').classes('font-bold text-sm')
                        for outlet in node.outlets.values():
                            ui.label(outlet.label).classes('text-xs text-right')
        
        return UINodeCard(main_card, ui_elements, widget_instances)
    

    def render_element(self, element_type: str, element, ui_elements: Dict[str, Any], widget_instances: Dict[str, Any]) -> Element | None:
        """Render a single element using widget registry"""
        if not element.data or element.widget is None:
            return None
        
        # Get widget name and properties
        widget_name = element.widget
        
        try:
            # Get widget instance from registry (with fallback strategy depending on data type)
            widget_instance, lc_event = self._render_factory.get_widget_instance(widget_name, element)
            
            if widget_instance is not None:
                
                # Render the widget
                ui_element = widget_instance.render()
                            
                # Store references
                ui_elements[element.id] = ui_element
                widget_instances[element.id] = widget_instance
                
                return ui_element
            else:
                return None
            
        except Exception as e:
            # Fallback to error display if widget creation fails
            creationerror = NodeErrorInfo(
                error='Widget Creation Error',
                error_message=str(e)
            )
            creationerror.add_note(f"Element: {element.id}")
            creationerror.add_note(f"Requested widget: {getattr(element, 'widget', 'None')}")

            return render_error_info(creationerror)

