
from typing import Any, Dict
from nicegui import ui
from nicegui.element import Element
from haywire.core.node.node_wrapper import NodeWrapper
from haywire.core.node.base import BaseNode
from haywire.ui.themes.colors import Theme_UI_Color
from haywire.ui.themes.palette import ThemePalette
from haywire.ui.ui_nodecard import UINodeCard
from haywire.core.ui.widget.base import BaseWidget
from haywire.core.ui.renderer.decorator import renderer

from haywire.libraries.core.nodes.node_renderer import NodeRenderer

@renderer(
    description="Custom renderer for nodes with special styling"
    )
class ExampleNodeRenderer(NodeRenderer):
    """Custom renderer for nodes with special styling."""

    def render(self, main_card: ui.card, wrapper: NodeWrapper):

        ui_elements = {}
        widget_instances: Dict[str, BaseWidget] = {}
        
        node: BaseNode = wrapper.node
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

        main_card.classes(
            f'w-full min-w-64 max-w-sm math-node-card {node_id}'
        )       

        with main_card:
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
                                        widget = self.render_widget(inlet, wrapper.node_id)
                
                # Outlets
                with ui.column().classes('flex-1 gap-1'):
                    if node.outlets:
                        ui.label('Outputs').classes('font-bold text-sm')
                        for outlet in node.outlets.values():
                            ui.label(outlet.label).classes('text-xs text-right')
        
    