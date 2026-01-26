"""
Default NodeRenderer with group support

This renderer provides the standard node appearance with collapsible groups
"""

from typing import List
from haywire.ui.widget.factory import error_render_detail
from nicegui import ui

from haywire.core.node.node_wrapper import NodeWrapper
from haywire.core.types.ports import DataPort

from haywire.ui.renderer.decorator import renderer
from haywire.ui.themes.keys import ThemeKey
from haywire.ui.themes import ThemePalette

from ..renderers.node_renderer import NodeRenderer

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
            # Header with node label
            with ui.row().classes('drag-handle'):
                ui.label(node.identity.label).classes('text-h6')
           
                if wrapper.state and wrapper.state.has_error():
                    error = wrapper.state.get_error()
                    ui.label(error.message).classes('text-sm text-red-600 mb-2')
                    error_render_detail(error)

            # Main content: inlets and outlets in two columns
            with ui.row().classes('w-full gap-2'):
                # Left column: Inlets
                with ui.column().classes('flex-1 gap-1'):
                    # Root ghost pin for inlet (fallback when all ports hidden)
                    self._render_root_ghost_pin(wrapper, is_inlet=True)
                    
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
                        
                # Right column: Outlets
                with ui.column().classes('flex-1 gap-1'):
                    # Root ghost pin for outlet (fallback when all ports hidden)
                    self._render_root_ghost_pin(wrapper, is_inlet=False)

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
                if not is_expanded:
                    # Group is collapsed - render ghost pin if needed
                    self._render_ghost_pin(group_port, wrapper, is_inlet)

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

    
    def _render_ghost_pin(self,
                         group_port: DataPort,
                         wrapper: NodeWrapper,
                         is_inlet: bool):
        """
        Render a ghost pin for collapsed groups with connections.
        
        Ghost pins provide a visual target for connections to ports
        that are hidden inside collapsed groups. They are:
        - Semi-transparent (50% opacity)
        - Not interactive (pointer-events: none)
        - Only shown if any child has connections
        
        Args:
            group_port: The group control port
            wrapper: NodeWrapper containing the node
            is_inlet: True if rendering in inlet column
        """
        node = wrapper.node
        
        # Check if any children have connections
        has_connections = False
        for port in node.ports.values():
            if port.parent_group == group_port.id:
                if port.is_linked():
                    has_connections = True
                    break
        
        if not has_connections:
            return
        
        # Render semi-transparent ghost pin
        # UUID format MUST match Vue: {port_id}@{node_id}
        direction = 'left' if is_inlet else 'right'
        pin_uuid = f"{group_port.id}@{wrapper.node_id}"
        
        # Ghost pin with connection data for graph renderer
        ui.icon('radio_button_unchecked', 
                color='gray', 
                size='15px').classes(
            'connection-pin ghost-pin opacity-50'
        ).style(
            f'position: absolute; {direction}: -20px; '
            f'pointer-events: none;'  # Not interactive!
        ).props(
            f'id="{pin_uuid}" '
            f'data-ghost-group="{group_port.id}" '
            f'data-node-id="{wrapper.node_id}" '
            f'data-pin-id="{group_port.id}" '
            f'data-pin-dir="{"inlet" if is_inlet else "outlet"}" '
            f'data-pin-flow-type="{group_port.flow_type.value}" '
            f'data-pin-color="#888888"'
        )
        
        # Optional: Add tooltip indicating this is a ghost pin
        with ui.element().style('position: relative;'):
            ui.tooltip(
                f'Collapsed group "{group_port.label}" has connections'
            ).classes('text-xs')
    
    def _render_root_ghost_pin(self, wrapper: NodeWrapper, is_inlet: bool):
        """
        Render root-level ghost pin for the node.
        
        Root ghost pins are the ultimate fallback for connections when
        all ports are hidden/removed. Each node has:
        - One root inlet ghost pin (left side)
        - One root outlet ghost pin (right side)
        
        These pins use the special port ID 'root' and are always rendered,
        though typically invisible unless needed.
        
        Args:
            wrapper: NodeWrapper containing the node
            is_inlet: True for inlet ghost pin, False for outlet
        """
        # UUID format MUST match Vue: root@{node_id}
        direction = 'left' if is_inlet else 'right'
        pin_uuid = f"root@{wrapper.node_id}"
        flow_type = 'data'  # Root pins handle data connections
        
        # Root ghost pin - always present as ultimate fallback
        ui.icon('radio_button_unchecked',
                color='gray',
                size='12px').classes(
            'connection-pin root-ghost-pin opacity-30'
        ).style(
            f'position: absolute; {direction}: -20px; top: 50%; '
            f'transform: translateY(-50%); '
            f'pointer-events: auto;'  # Root pins ARE interactive
        ).props(
            f'id="{pin_uuid}" '
            f'data-node-id="{wrapper.node_id}" '
            f'data-pin-id="root" '
            f'data-pin-dir="{"inlet" if is_inlet else "outlet"}" '
            f'data-pin-flow-type="{flow_type}" '
            f'data-pin-color="#666666"'
        )