"""
Default NodeRenderer

This renderer provides the standard node appearance and functionality
"""

from nicegui import ui

from haywire.core.node.node_wrapper import NodeWrapper

from haywire.ui.renderer.decorator import renderer
from haywire.ui.themes.colors import Theme_UI_Color
from haywire.ui.themes import ThemePalette

from haywire.libraries.core.renderers.node_renderer import NodeRenderer

@renderer(
    description="Default renderer that provides the standard node appearance", 
    _is_default=True)
class DefaultNodeRenderer(NodeRenderer):
    """
    Default renderer that provides the standard node appearance.
    
    This is based on the existing ModularNiceGUINodeRenderer design
    and serves as the fallback renderer when no specific renderer is requested.
    """
    
    def render(self, main_card: ui.card, wrapper: NodeWrapper):
        node = wrapper.node

        node_bg = ThemePalette.ui(Theme_UI_Color.NODE_BACKGROUND, 'rgba(255, 255, 255, 0.3)')
        main_card.classes(
            'w-full min-w-64 max-w-sm node-card zoom-pan-lod0'
        ).style(
            f'background-color: {node_bg}; backdrop-filter: blur(10px);'
        )        

        with main_card:
            with ui.row().classes('drag-handle'):
                ui.label(node.identity.label).classes('text-h6')

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
            with ui.row().classes('w-full justify-between mt-2 zoom-pan-lod1'):
                ui.label(f'↓ {len([p for p in node.ports.values() if p.is_inlet()])}').classes('text-caption')
                ui.label(f'↑ {len([p for p in node.ports.values() if p.is_outlet()])}').classes('text-caption')
           