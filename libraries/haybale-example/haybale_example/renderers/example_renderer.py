
from typing import Any, Dict
from nicegui import ui
from nicegui.element import Element
from haywire.core.node.dataclasses import NodeErrorInfo
from haywire.core.node.node_wrapper import NodeWrapper
from haywire.core.types.ports import PortInlet
from haywire.core.ui.base_renderer import BaseNodeRenderer
from haywire.core.node.base_node import BaseNode
from haywire.core.ui.base import UINodeCard
from haywire.core.ui.base_widget import BaseWidget
from haywire.core.ui.base_renderer import renderer
from haywire.ui.utils import render_error_info

@renderer(description="Custom renderer for nodes with special styling")
class ExampleNodeRenderer(BaseNodeRenderer):
    """Custom renderer for nodes with special styling."""

    def _render(self, wrapper: NodeWrapper) -> UINodeCard:
        """Render a node with custom styling."""
        ui_elements = {}
        widget_instances: Dict[str, BaseWidget] = {}
        
        node = wrapper.node
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
                                    if inlet.widget:
                                        widget = self._render_factory.render_widget(inlet, node.node_id)
                                        if widget:
                                            widget_instances[inlet.id] = widget
                
                # Outlets
                with ui.column().classes('flex-1 gap-1'):
                    if node.outlets:
                        ui.label('Outputs').classes('font-bold text-sm')
                        for outlet in node.outlets.values():
                            ui.label(outlet.label).classes('text-xs text-right')
        
        return UINodeCard(main_card, ui_elements, widget_instances)
    