
from nicegui import ui
from haywire.core.ui.renderer import BaseNodeRenderer
from haywire.core.node.node import BaseNode
from haywire.core.ui.base import UINodeCard 

class ExampleNodeRenderer(BaseNodeRenderer):
    """Custom renderer for nodes with special styling."""

    def render(self, node: BaseNode) -> UINodeCard:
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
                                    self._render_element(inlet, ui_elements, widget_instances)
                
                # Outlets
                with ui.column().classes('flex-1 gap-1'):
                    if node.outlets:
                        ui.label('Outputs').classes('font-bold text-sm')
                        for outlet in node.outlets.values():
                            ui.label(outlet.label).classes('text-xs text-right')
        
        return UINodeCard(main_card, ui_elements, widget_instances)
    
    def _render_element(self, element, ui_elements, widget_instances):
        """Render element using widget registry."""
        if not element.data or element.widget == 'None':
            return
        
        try:
            widget_class = self.widget_registry.get_widget_class(element.widget, element.data)
            widget_instance = widget_class(element)
            ui_element = widget_instance.render()
            
            if hasattr(ui_element, 'classes'):
                ui_element.classes('widget-container')
            
            ui_elements[element.id] = ui_element
            widget_instances[element.id] = widget_instance
            
        except Exception as e:
            with ui.column().classes('w-full p-2 border border-red-300 bg-red-100 widget-container') as error_widget:
                ui.label(f"Widget Error: {str(e)}").classes('text-red-700 text-sm')
            ui_elements[element.id] = error_widget
            widget_instances[element.id] = None
