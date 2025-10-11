"""
Error NodeRenderer - Based on the DefaultNodeRenderer

This renderer provides error styling for nodes.
"""

from typing import Dict, Any
from nicegui import ui
from haywire.core.node.node import BaseNode, NodeErrorInfo
from haywire.core.ui.base import UINodeCard
from haywire.ui.utils import render_error_info
from haywire.core.inventory.registry.renderer_reg import renderer

from .default_renderer import DefaultNodeRenderer

@renderer(description="Error renderer that provides error styling for nodes", is_error=True)
class ErrorNodeRenderer(DefaultNodeRenderer):
    """
    Error renderer that provides error styling for nodes.
    
    This is a child class of DefaultNodeRenderer with different styling
    to indicate rendering errors or fallback situations.
    """
    
    def render(self, node: BaseNode) -> UINodeCard:
        """
        Render a node with error styling.
        
        Args:
            node: The HaywireNode to render
            
        Returns:
            UINodeCard containing the rendered UI with error styling
        """
        # Storage for UI elements and widget instances
        ui_elements: Dict[str, Any] = {}
        widget_instances: Dict[str, Any] = {}
        
        # Generate unique node ID for CSS scoping
        node_id = f"error-node-{id(node)}"
        
        # Add CSS for error styling
        ui.add_head_html(f'''
        <style>
        .{node_id} {{
            border: 2px solid #ef4444;
            background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%);
            transition: all 0.2s ease;
        }}
        .{node_id} .text-h6 {{
            color: #dc2626;
        }}
        .{node_id} .widget-container {{
            opacity: 0;
            transition: opacity 0.3s ease;
            max-height: 0;
            overflow: hidden;
        }}
        .{node_id}:hover .widget-container,
        .{node_id}:focus-within .widget-container {{
            opacity: 1;
            max-height: 200px;
        }}
        .{node_id}:hover,
        .{node_id}:focus-within {{
            box-shadow: 0 4px 12px rgba(239, 68, 68, 0.3);
        }}
        </style>
        ''')
        
        # Create the main card with error styling
        with ui.card().classes(f'w-full min-w-64 max-w-sm error-node-card {node_id}') as main_card:
            # Error header
            if node and node.error_info:
                render_error_info(node.error_info)
            else:
                with ui.column().classes('items-left'):
                    with ui.row():
                        ui.icon('error', color='red').classes('text-lg')
                        ui.label("Error Node").classes('text-h6 flex-1')
                
                    ui.label('This node could not be rendered with the requested renderer.').classes('text-sm text-red-600 mb-2')
            
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
            with ui.row().classes('w-full justify-between mt-2'):
                ui.label(f'↓ {len(node.inlets)}').classes('text-caption')
                ui.label(f'↑ {len(node.outlets)}').classes('text-caption')
        
        return UINodeCard(main_card, ui_elements, widget_instances)
