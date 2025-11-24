"""
Default NodeRenderer

This renderer provides the standard node appearance and functionality
"""

from typing import Dict, Any
from nicegui import ui
from nicegui.element import Element

from haywire.core.node.node_wrapper import NodeWrapper
from haywire.core.ui.widget.base import BaseWidget
from haywire.core.ui.renderer.decorator import renderer
from haywire.ui.renderer.node_renderer import NodeRenderer
from haywire.ui.ui_nodecard import UINodeCard
from haywire.ui.themes.colors import Theme_UI_Color
from haywire.ui.themes import ThemePalette

@renderer(
    description="Default renderer that provides the standard node appearance", 
    is_default=True)
class DefaultNodeRenderer(NodeRenderer):
    """
    Default renderer that provides the standard node appearance.
    
    This is based on the existing ModularNiceGUINodeRenderer design
    and serves as the fallback renderer when no specific renderer is requested.
    """
    
    def render(self, main_card: ui.card, wrapper: NodeWrapper):
        node = wrapper.node
        # Storage for UI elements and widget instances
        ui_elements: Dict[str, Any] = {}
        widget_instances: Dict[str, BaseWidget] = {}

        node_bg = ThemePalette.ui(Theme_UI_Color.NODE_BACKGROUND, 'rgba(255, 255, 255, 0.3)')
        main_card.classes(
            f'w-full min-w-64 max-w-sm node-card zoom-pan-lod0'
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
                    if node.inlets:
                        ui.label('Inputs').classes('font-bold text-sm')
                        for inlet in node.inlets.values():
                            self._render_inlet(inlet, wrapper)

                # Right column: Outlets
                with ui.column().classes('flex-1 gap-1'):
                    if node.outlets:
                        ui.label('Outputs').classes('font-bold text-sm')
                        for outlet in node.outlets.values():
                            self._render_outlet(outlet, wrapper)

            # Footer with port counts
            with ui.row().classes('w-full justify-between mt-2 zoom-pan-lod1'):
                ui.label(f'↓ {len(node.inlets)}').classes('text-caption')
                ui.label(f'↑ {len(node.outlets)}').classes('text-caption')
           