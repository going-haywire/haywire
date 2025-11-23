"""
Error NodeRenderer - Based on the DefaultNodeRenderer

This renderer provides error styling for nodes.
"""

from typing import Dict, Any
from nicegui import ui

from haywire.core.errors.haywire_exception import HaywireException
from haywire.core.node.base_node import BaseNode
from haywire.core.node.node_wrapper import NodeWrapper
from haywire.ui.niceui_node_renderer import NiceUINodeRenderer
from haywire.ui.ui_nodecard import NiceUINodeCard
from haywire.ui.errors.haywire_exception import render_error_details
from haywire.ui.utils import render_error_info
from haywire.core.ui.renderer.decorator import renderer

@renderer(
    description="Error renderer that provides error styling for nodes", 
    is_error=True)
class ErrorNodeRenderer(NiceUINodeRenderer):
    """
    Error renderer that provides error styling for nodes.
    
    This is a child class of DefaultNodeRenderer with different styling
    to indicate rendering errors or fallback situations.
    """
    
    def render(self, wrapper: NodeWrapper) -> NiceUINodeCard:
        """
        Render a node with error styling.
        
        Args:
            wrapper: The NodeWrapper containing the HaywireNode to render
            
        Returns:
            UINodeCard containing the rendered UI with error styling
        """
        node: BaseNode = wrapper.node
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
            
            if wrapper.state.error:
                error = wrapper.state.error
                
                if not error or not isinstance(error, HaywireException):
                    # Create a default error if none provided
                    error = HaywireException.create(
                        message="An error occurred but no detailed information is available",
                        category="Unknown Error"
                    )

                with ui.column().classes('w-full') as container:
                # Compact error summary card
                    with ui.card().classes('w-full bg-red-50 border-l-4 border-red-500 shadow-sm'):
                        with ui.row().classes('items-start gap-3 w-full'):
                            # Icon
                            ui.icon(error.get_severity_icon(), color=error.get_severity_color()).classes('text-2xl')
                            
                            # Error message and button
                            with ui.column().classes('flex-grow gap-1'):
                                ui.label(f"{error.category}").classes('text-red-700 font-bold text-sm')
                                ui.label(error.message).classes('text-gray-800 text-sm')
                                
                                with ui.row().classes('gap-2 mt-2'):
                                    detail_button = ui.button('Show Details', icon='expand_more').classes('bg-red-600 text-white')
                    
                    # Create dialog with lazy content rendering
                    dialog = ui.dialog()
                    
                    def show_details():
                        """Render error details on-demand when dialog is opened"""
                        # Clear any existing content
                        dialog.clear()
                        
                        # Create the dialog content NOW (lazy rendering)
                        with dialog, ui.card().classes('w-full max-w-4xl bg-gray-50'):
                            with ui.column().classes('w-full gap-4 p-4'):
                                # Render error details using the reusable function
                                detail_container = ui.column().classes('w-full gap-4')
                                render_error_details(error, detail_container)
                                
                                # Footer with close button
                                with ui.row().classes('justify-end w-full pt-3 border-t'):
                                    ui.button('Close', icon='close', on_click=dialog.close).classes('bg-gray-600 text-white')
                        
                        # Open the dialog
                        dialog.open()
                    
                    # Connect button to lazy rendering function
                    detail_button.on_click(show_details)  



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
        
        return NiceUINodeCard(main_card, ui_elements, widget_instances)
