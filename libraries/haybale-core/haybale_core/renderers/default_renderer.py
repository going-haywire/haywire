"""
Default NodeRenderer with group support

This renderer provides the standard node appearance with collapsible groups
"""

from typing import List, TYPE_CHECKING
from haywire.ui.widget.factory import error_render_detail
from nicegui import ui

from haywire.core.node.node_wrapper import NodeWrapper
from haywire.core.types.ports import DataPort

from haywire.ui.renderer.decorator import renderer
from haywire.ui.themes.keys import ThemeKey
from haywire.ui.themes import ThemePalette

from ..renderers.node_renderer import NodeRenderer

if TYPE_CHECKING:
    from haywire.core.node.base import BaseNode
    from haywire.core.errors import HaywireException

@renderer(
    description="Default renderer with collapsible group support", 
    _is_default=True)
class DefaultNodeRenderer(NodeRenderer):
    """
    Default renderer that provides the standard node appearance with group support.
    
    Features:
    - Two-column layout (inlets left, outlets right)
    - Collapsible groups with visual hierarchy
    - Ghost pins for collapsed groups with connections
    - Automatic port ordering
    """
    
    def render(self, main_card: ui.card, wrapper: NodeWrapper):
        """Render the complete node UI with groups."""
        node = wrapper.node

        node_bg = ThemePalette.get(
            ThemeKey.UI_NODE_BACKGROUND,
            fallback='rgba(255, 255, 255, 0.3)'
        )
        main_card.classes(
            'w-full min-w-64 max-w-sm node-card zoom-pan-lod0'
        ).style(
            f'background-color: {node_bg}; backdrop-filter: blur(10px);'
        )        

        with main_card:
            # Header with node label and ghost pins for hidden connected ports
            with ui.row().classes('drag-handle w-full items-center'):
                # Ghost pins for hidden inlet connections (left side)
                hidden_inlets = node.get_hidden_connected_ports(is_inlet=True)
                if hidden_inlets:
                    with ui.column().classes('gap-0 items-center'):
                        for port in hidden_inlets:
                            self._render_pin(port, wrapper, direction='left')
                
                # Node title (centered/flexible)
                ui.label(node.identity.label).classes('text-h6 flex-grow')
                
                # Ghost pins for hidden outlet connections (right side)
                hidden_outlets = node.get_hidden_connected_ports(is_inlet=False)
                if hidden_outlets:
                    with ui.column().classes('gap-0 items-center'):
                        for port in hidden_outlets:
                            self._render_pin(port, wrapper, direction='right')
           
                if wrapper.state and wrapper.state.has_error():
                    error = wrapper.state.get_error()
                    ui.label(error.message).classes('text-sm text-red-600 mb-2')
                    error_render_detail(error)

                    if wrapper._alternate_registry_keys:
                        ui.label(
                            f"Alternate versions available: "
                            f"{', '.join(wrapper._alternate_registry_keys)}"
                        ).classes('text-sm text-yellow-600 mb-2')
                
                # Runtime errors indicator with popup
                runtime_errors = wrapper._get_all_runtime_errors()
                if runtime_errors:
                    self._render_runtime_errors_button(runtime_errors)

            # Main content: inlets and outlets in two columns
            with ui.row().classes('w-full gap-2'):
                # Left column: Inlets
                with ui.column().classes('flex-1 gap-1'):                    
                    if node.ports:
                        self._render_port_hierarchy(
                            node.get_visible_ports(),
                            wrapper,
                            is_inlet=False
                        )
                    if node.ports:
                        self._render_port_hierarchy(
                            node.get_visible_ports(),
                            wrapper,
                            is_inlet=True
                        )
                        
            # Footer with port counts
            with ui.row().classes('w-full justify-between mt-2 zoom-pan-lod1'):
                ui.label(f'↓ {len([p for p in node.ports.values() if p.is_inlet])}').classes('text-caption')
                ui.label(f'↑ {len([p for p in node.ports.values() if p.is_outlet])}').classes('text-caption')

        # Add resize handle in bottom-right corner
        self._add_resize_handle(main_card, wrapper)

    def _render_port_hierarchy(self, 
                               ports: List[DataPort],
                               wrapper: NodeWrapper,
                               is_inlet: bool):
        """
        Render ports with hierarchical group structure.
        
        Only renders top-level ports - child ports are rendered
        recursively inside their parent groups.
        
        Args:
            ports: List of visible ports (from get_visible_ports())
            wrapper: NodeWrapper containing the node
            is_inlet: True to render inlets, False for outlets
        """
        for port in ports:
            # Skip ports of wrong direction
            if port.is_inlet != is_inlet:
                continue
            
            # Skip child ports (they're rendered inside their parent group)
            if port.parent_group:
                continue
            
            # Render based on port type
            if port.is_group:
                self._render_group(port, ports, wrapper, is_inlet)
            else:
                if is_inlet:
                    self._render_inlet(port, wrapper, widget_classes='widget-container zoom-pan-lod2')
                else:
                    self._render_outlet(port, wrapper, widget_classes='widget-container zoom-pan-lod2')
    
    def _render_group(self,
                     group_port: DataPort,
                     all_ports: List[DataPort],
                     wrapper: NodeWrapper,
                     is_inlet: bool):
        """
        Render a collapsible group with visual hierarchy.
        
        Groups are rendered with:
        - Border and indentation for visual hierarchy
        - Group header with toggle widget
        - Child ports (if expanded)
        - Ghost pin (if collapsed with connections)
        
        Args:
            group_port: The group control port (boolean inlet)
            all_ports: All visible ports (to find children)
            wrapper: NodeWrapper containing the node
            is_inlet: True if rendering in inlet column
        """
        node = wrapper.node
        is_expanded = node.value(group_port.id)
        
        # Group container with visual hierarchy
        with ui.column().classes('w-full pl-2 ml-1 gap-1'):
            # Group header with toggle
            with ui.row().classes('w-full items-center gap-1'):
                # Render group toggle widget
                if group_port.widget_key:
                    self.render_widget(group_port, wrapper.node_id, classes='zoom-pan-lod2')
            
            # Group children (if expanded)
            if is_expanded:
                # Find and render direct children
                children = [
                    port for port in all_ports
                    if port.parent_group == group_port.id and port.is_inlet == is_inlet
                ]
                
                for child_port in sorted(children, key=lambda p: p.order):
                    # Recursively handle nested groups
                    if child_port.is_group:
                        self._render_group(child_port, all_ports, wrapper, is_inlet)
                    else:
                        if is_inlet:
                            self._render_inlet(child_port, wrapper, widget_classes='widget-container zoom-pan-lod2')
                        else:
                            self._render_outlet(child_port, wrapper, widget_classes='widget-container zoom-pan-lod2')

    def _render_runtime_errors_button(self, errors: List['HaywireException']):
        """
        Render a button that shows runtime errors count and opens a popup with details.
        
        Args:
            errors: List of runtime errors to display
        """
        error_count = len(errors)
        
        with ui.button(
            icon='warning',
            color='red'
        ).classes('text-xs px-2 py-1').props('dense flat') as btn:
            ui.badge(str(error_count), color='red').props('floating')
            
            with ui.menu().props('anchor="bottom left" self="top left"'):
                with ui.card().classes('p-2 max-w-md max-h-96 overflow-auto'):
                    ui.label(
                        f'Runtime Errors ({error_count})'
                    ).classes('text-subtitle2 font-bold mb-2')
                    
                    for idx, error in enumerate(errors):
                        with ui.expansion(
                            f'{idx + 1}. {error.operation or "Error"}',
                            icon='error'
                        ).classes('w-full text-red-600'):
                            ui.label(error.message).classes(
                                'text-sm text-red-600 mb-2'
                            )
                            error_render_detail(error)

