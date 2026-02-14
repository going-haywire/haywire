"""
Error NodeRenderer - Based on the DefaultNodeRenderer

This renderer provides error styling for nodes.
"""

from nicegui import ui

from haywire.core.node.base import BaseNode
from haywire.core.node.node_wrapper import NodeWrapper

from haywire.ui.renderer.decorator import renderer
from haywire.ui.themes.keys import ThemeKey
from haywire.ui.themes.palette import ThemePalette
from haywire.ui.errors.error_info import error_render_detail


from ..renderers.node_renderer import NodeRenderer

@renderer(
    description="Error renderer that provides error styling for nodes", 
    _is_error=True)
class ErrorNodeRenderer(NodeRenderer):
    """
    Error renderer that provides error styling for nodes.
    
    This is a child class of DefaultNodeRenderer with different styling
    to indicate rendering errors or fallback situations.
    """
    
    def render(self, main_card: ui.card, wrapper: NodeWrapper):

        node: BaseNode = wrapper.node
        
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

        node_bg = ThemePalette.get(
            ThemeKey.UI_WARNING,
            fallback='rgba(255, 255, 255, 0.3)'
        )
        main_card.classes(
            f'w-full min-w-64 max-w-sm error-node-card {node_id} zoom-pan-lod0'
        ).style(
            f'background-color: {node_bg}; backdrop-filter: blur(10px);'
        )        

        with main_card:
            # Error header
            with ui.column().classes('items-left'):
                with ui.row():
                    ui.label(node.identity.label).classes('text-h6')
            
                 # Runtime errors indicator with popup
                runtime_errors = wrapper.state.get_errors()
                if runtime_errors:
                    self._render_errors_button(runtime_errors)

            # Main content: inlets and outlets in two columns
            with ui.row().classes('w-full gap-2'):
                # Left column: Inlets
                with ui.column().classes('flex-1 gap-1'):
                    if node.ports:
                        ui.label('Inputs').classes('font-bold text-sm')
                        for inlet in node.ports.values():
                            if inlet.is_inlet():
                                self._render_inlet(inlet, wrapper)

                # Right column: Outlets
                with ui.column().classes('flex-1 gap-1'):
                    if node.ports:
                        ui.label('Outputs').classes('font-bold text-sm')
                        for outlet in node.ports.values():
                            if outlet.is_outlet():
                                self._render_outlet(outlet, wrapper)

            # Footer with port counts
            with ui.row().classes('w-full justify-between mt-2'):
                ui.label(f'↓ {len([p for p in node.ports.values() if p.is_inlet()])}').classes('text-caption')
                ui.label(f'↑ {len([p for p in node.ports.values() if p.is_outlet()])}').classes('text-caption')
        
