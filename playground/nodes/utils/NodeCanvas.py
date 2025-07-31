"""
Node Graph component for rendering the entire graph canvas
"""

from typing import Dict, List, Any
from nicegui import ui
from utils.NodePanel import NodePanel
from utils.node import Node
from controllers.ToolbarController import ToolbarController

class NodeCanvas:
    """Handles rendering and interaction for the entire node graph"""
    
    def __init__(self, graph_manager):
        self.graph_manager = graph_manager
        self.node_editors: Dict[str, NodePanel] = {}
        self.canvas_element = None
        self.connection_svg = None
        # Register with graph manager for UI updates
        self.graph_manager.set_node_graph(self)
        # Create toolbar controller
        self.toolbar_controller = ToolbarController(graph_manager, self)
        
    def render(self):
        """Render the node graph canvas"""
        with ui.column().classes('w-full h-full relative') as canvas:
            # Graph canvas background
            with ui.element('div').classes(
                'w-full h-full relative graph-canvas'
            ).style(
                'background: #fafafa; '
                'background-image: '
                'linear-gradient(#e0e0e0 1px, transparent 1px), '
                'linear-gradient(90deg, #e0e0e0 1px, transparent 1px); '
                'background-size: 20px 20px; '
                'overflow: hidden; '
                'min-height: 600px;'
            ) as graph_canvas:
                
                # SVG overlay for connections
                with ui.element('svg').classes('absolute inset-0 w-full h-full pointer-events-none') as svg:
                    svg.props('width="100%" height="100%"')
                    self.connection_svg = svg
                
                # Container for nodes
                with ui.element('div').classes('absolute inset-0 w-full h-full') as node_container:
                    self.node_container = node_container
                
                # Add event handlers for canvas interactions
                # Use simpler event handlers for better compatibility
                graph_canvas.on('click', self._on_canvas_click)
                # Add global mouse event handlers for dragging
                graph_canvas.on('mousemove', self._on_canvas_mouse_move, args=[
                    'clientX', 'clientY'
                ])
                graph_canvas.on('mouseup', self._on_canvas_mouse_up)
                
            self.canvas_element = canvas
            
            # Control panel - delegated to ToolbarController
            self.toolbar_controller.render_toolbar()
        
        # Start the update loop
        self._update_loop()
    
    def _update_loop(self):
        """Update the graph display periodically"""
        # Check for new nodes
        for node_id, node in self.graph_manager.nodes.items():
            if node_id not in self.node_editors:
                self._add_node_editor(node)
        
        # Check for removed nodes
        nodes_to_remove = []
        for node_id in self.node_editors:
            if node_id not in self.graph_manager.nodes:
                nodes_to_remove.append(node_id)
        
        for node_id in nodes_to_remove:
            self._remove_node_editor(node_id)
        
        # Update connections
        self._update_connections()
        
        # Schedule next update
        ui.timer(0.1, self._update_loop, once=True)
    
    def _add_node_editor(self, node: Node):
        """Add a node editor for a new node"""
        with self.node_container:
            editor = NodePanel(node, self)
            editor.render()
            self.node_editors[node.id] = editor
    
    def _remove_node_editor(self, node_id: str):
        """Remove a node editor"""
        if node_id in self.node_editors:
            # The UI element should be automatically removed when the node is deleted
            del self.node_editors[node_id]
    
    def _update_connections(self):
        """Update the connection lines between nodes"""
        if not self.connection_svg:
            return
            
        # Clear existing connections
        self.connection_svg.clear()
        
        # Draw each connection
        for connection in self.graph_manager.connections.values():
            self._draw_connection(connection.source_port_id, connection.target_port_id)
    
    def _draw_connection(self, source_port_id: str, target_port_id: str):
        """Draw a connection line between two ports"""
        # Find the source and target ports
        source_port = self.graph_manager._find_port(source_port_id)
        target_port = self.graph_manager._find_port(target_port_id)
        
        if not source_port or not target_port:
            return
        
        # Calculate port positions (simplified)
        source_node = None
        target_node = None
        
        for node in self.graph_manager.nodes.values():
            if source_port in node.outputs:
                source_node = node
            if target_port in node.inputs:
                target_node = node
        
        if not source_node or not target_node:
            return
        
        # Calculate connection points
        source_x = source_node.x + source_node.width
        source_y = source_node.y + source_node.height / 2
        target_x = target_node.x
        target_y = target_node.y + target_node.height / 2
        
        # Create curved connection
        control_point_offset = abs(target_x - source_x) * 0.5
        control1_x = source_x + control_point_offset
        control1_y = source_y
        control2_x = target_x - control_point_offset
        control2_y = target_y
        
        # SVG path for curved line
        path_data = (
            f"M {source_x} {source_y} "
            f"C {control1_x} {control1_y} {control2_x} {control2_y} {target_x} {target_y}"
        )
        
        # Add the path to the SVG
        with self.connection_svg:
            ui.element('path').props(
                f'd="{path_data}" '
                f'stroke="#666" '
                f'stroke-width="2" '
                f'fill="none" '
                f'marker-end="url(#arrowhead)"'
            )
        
        # Add arrowhead marker (define once)
        if not hasattr(self, '_arrowhead_defined'):
            with self.connection_svg:
                with ui.element('defs'):
                    with ui.element('marker').props(
                        'id="arrowhead" '
                        'markerWidth="10" '
                        'markerHeight="7" '
                        'refX="9" '
                        'refY="3.5" '
                        'orient="auto"'
                    ):
                        ui.element('polygon').props(
                            'points="0 0, 10 3.5, 0 7" '
                            'fill="#666"'
                        )
            self._arrowhead_defined = True
    
    def _on_canvas_click(self, e):
        """Handle canvas click events"""
        # Clear selection when clicking on empty canvas
        # NiceGUI's GenericEventArguments doesn't have target property
        # For now, always clear selection on canvas click
        self.graph_manager.clear_selection()
    
    def _on_canvas_mouse_move(self, e):
        """Handle mouse move events for dragging"""
        client_x = e.args.get('clientX', 0)
        client_y = e.args.get('clientY', 0)
        
        # Update any dragging nodes
        for editor in self.node_editors.values():
            if editor.is_dragging():
                editor.update_drag_position(client_x, client_y)
    
    def _on_canvas_mouse_up(self, e):
        """Handle mouse up events to end dragging"""
        # End dragging for all nodes
        for editor in self.node_editors.values():
            if editor.is_dragging():
                editor.end_local_drag()
    
    def _reset_node_cursors(self):
        """Reset cursor style for all nodes after dragging ends"""
        for editor in self.node_editors.values():
            if hasattr(editor, 'node_card') and editor.node_card:
                editor.node_card.style('cursor: grab;')
    
    def _on_canvas_context_menu(self, e):
        """Handle canvas right-click for context menu"""
        # NiceGUI handles preventDefault differently
        # In a real application, show a context menu here
        self.graph_manager.notification_service.notify("Right-click menu not implemented")
    
    # Node operations - interface between NodeEditor and GraphManager
    def remove_node(self, node_id: str):
        """Remove a node from the graph"""
        self.graph_manager.remove_node(node_id)
    
    def select_node(self, node_id: str, multi_select: bool = False):
        """Select a node"""
        self.graph_manager.select_node(node_id, multi_select)
    
    def update_node_property(self, node_id: str, key: str, value: Any):
        """Update a node property"""
        self.graph_manager.status_message = f"Updated {self.graph_manager.nodes[node_id].name} property: {key}"
    
    # Event handlers for node drag operations
    def on_node_drag_started(self, node_id: str):
        """Called when a node starts being dragged"""
        self.graph_manager.on_node_drag_started(node_id)
    
    def on_node_position_changed(self, node_id: str, x: float, y: float):
        """Called when a node position changes during drag"""
        self.graph_manager.on_node_position_changed(node_id, x, y)
    
    def on_node_drag_ended(self, node_id: str):
        """Called when a node drag operation ends"""
        self.graph_manager.on_node_drag_ended(node_id)
