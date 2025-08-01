---
## `utils/NodeCanvas.py`
---

```python
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
```

---
## `utils/Graph.py`
---

```python
"""
Utility functions for graph management
"""

from typing import Dict, List, Optional, Tuple
import json
from utils.node import Node, NodeType, Connection
from services.notification_service import NotificationService, NullNotificationService

class GraphManager:
    """Manages the node graph state and operations"""
    
    def __init__(self, notification_service: Optional[NotificationService] = None):
        self.nodes: Dict[str, Node] = {}
        self.connections: Dict[str, Connection] = {}
        self.selected_nodes: List[str] = []
        self.status_message = "Ready"
        self.node_count = 0
        self._node_graph = None  # Reference to NodeGraph for UI updates
        
        # Use dependency injection for notifications
        self.notification_service = notification_service or NullNotificationService()
        
    def add_node(self, node: Node) -> str:
        """Add a node to the graph"""
        self.nodes[node.id] = node
        self.node_count = len(self.nodes)
        self.status_message = f"Added {node.name} node"
        return node.id
    
    def add_node_simple(self, node_type_str: str) -> str:
        """Add a node from a type string (for testing)"""
        try:
            node_type = NodeType(node_type_str)
            # Calculate position to avoid overlapping
            x = 100 + (len(self.nodes) % 5) * 200
            y = 100 + (len(self.nodes) // 5) * 150
            
            node = Node.create(node_type, node_type_str.title(), x, y)
            return self.add_node(node)
        except ValueError:
            print(f"Unknown node type: {node_type_str}")
            return None
    
    def add_node_from_palette(self, node_type_str: str, name: str):
        """Add a node from the palette at a default position"""
        try:
            node_type = NodeType(node_type_str)
            # Calculate position to avoid overlapping
            x = 200 + (len(self.nodes) % 5) * 200
            y = 150 + (len(self.nodes) // 5) * 150
            
            node = Node.create(node_type, name, x, y)
            self.add_node(node)
            self.notification_service.notify_success(f"Added {name} node")
        except ValueError:
            self.notification_service.notify_error(f"Unknown node type: {node_type_str}")
    
    def remove_node(self, node_id: str):
        """Remove a node and its connections from the graph"""
        if node_id in self.nodes:
            node = self.nodes[node_id]
            
            # Remove all connections to/from this node
            connections_to_remove = []
            for conn_id, connection in self.connections.items():
                # Check if connection involves any port of this node
                for port in node.inputs + node.outputs:
                    if connection.source_port_id == port.id or connection.target_port_id == port.id:
                        connections_to_remove.append(conn_id)
                        break
            
            for conn_id in connections_to_remove:
                self.remove_connection(conn_id)
            
            # Remove the node
            del self.nodes[node_id]
            if node_id in self.selected_nodes:
                self.selected_nodes.remove(node_id)
            
            self.node_count = len(self.nodes)
            self.status_message = f"Removed {node.name} node"
    
    def add_connection(self, source_port_id: str, target_port_id: str) -> Optional[str]:
        """Add a connection between two ports"""
        # Validate connection
        source_port = self._find_port(source_port_id)
        target_port = self._find_port(target_port_id)
        
        if not source_port or not target_port:
            return None
        
        if source_port.is_input == target_port.is_input:
            self.notification_service.notify_error("Cannot connect two input or two output ports")
            return None
        
        # Ensure source is output and target is input
        if source_port.is_input:
            source_port, target_port = target_port, source_port
            source_port_id, target_port_id = target_port_id, source_port_id
        
        # Check if target already has a connection (single input per port)
        if target_port.connected_to:
            self.notification_service.notify_error("Input port already connected")
            return None
        
        # Create connection
        connection = Connection.create(source_port_id, target_port_id)
        self.connections[connection.id] = connection
        
        # Update port connections
        source_port.connected_to.append(target_port_id)
        target_port.connected_to.append(source_port_id)
        
        self.status_message = "Connection created"
        return connection.id
    
    def remove_connection(self, connection_id: str):
        """Remove a connection"""
        if connection_id in self.connections:
            connection = self.connections[connection_id]
            
            # Update port connections
            source_port = self._find_port(connection.source_port_id)
            target_port = self._find_port(connection.target_port_id)
            
            if source_port and connection.target_port_id in source_port.connected_to:
                source_port.connected_to.remove(connection.target_port_id)
            
            if target_port and connection.source_port_id in target_port.connected_to:
                target_port.connected_to.remove(connection.source_port_id)
            
            del self.connections[connection_id]
            self.status_message = "Connection removed"
    
    def _find_port(self, port_id: str):
        """Find a port by ID across all nodes"""
        for node in self.nodes.values():
            for port in node.inputs + node.outputs:
                if port.id == port_id:
                    return port
        return None
    
    def select_node(self, node_id: str, multi_select: bool = False):
        """Select a node"""
        if not multi_select:
            self.clear_selection()
        
        if node_id in self.nodes:
            self.selected_nodes.append(node_id)
            self.nodes[node_id].selected = True
    
    def clear_selection(self):
        """Clear all node selections"""
        for node_id in self.selected_nodes:
            if node_id in self.nodes:
                self.nodes[node_id].selected = False
        self.selected_nodes.clear()
        
    def set_node_graph(self, node_graph):
        """Set reference to NodeGraph for UI updates"""
        self._node_graph = node_graph
    
    # Event-based node drag handling
    def on_node_drag_started(self, node_id: str):
        """Handle when a node drag operation starts"""
        if node_id in self.nodes:
            node = self.nodes[node_id]
            self.status_message = f"Dragging {node.name}"
    
    def on_node_position_changed(self, node_id: str, x: float, y: float):
        """Handle when a node position changes"""
        # This is called during dragging - we don't need to do much here
        # since the position is already updated in the node model
        pass
    
    def on_node_drag_ended(self, node_id: str):
        """Handle when a node drag operation ends"""
        if node_id in self.nodes:
            node = self.nodes[node_id]
            self.status_message = f"Moved {node.name}"

    def move_node(self, node_id: str, x: float, y: float):
        """Move a node to a new position (for programmatic moves like keyboard)"""
        if node_id in self.nodes:
            self.nodes[node_id].set_position(x, y)
            # Update UI if NodeGraph is available
            if self._node_graph and node_id in self._node_graph.node_editors:
                self._node_graph.node_editors[node_id].update_position(x, y)


    def clear_graph(self):
        """Clear the entire graph"""
        self.nodes.clear()
        self.connections.clear()
        self.selected_nodes.clear()
        self.node_count = 0
        self.status_message = "Graph cleared"
        self.notification_service.notify("Graph cleared")
    
    def save_graph(self):
        """Save the graph to a JSON file"""
        try:
            graph_data = {
                'nodes': [
                    {
                        'id': node.id,
                        'type': node.node_type.value,
                        'name': node.name,
                        'x': node.x,
                        'y': node.y,
                        'width': node.width,
                        'height': node.height,
                        'properties': node.properties
                    }
                    for node in self.nodes.values()
                ],
                'connections': [
                    {
                        'id': conn.id,
                        'source_port_id': conn.source_port_id,
                        'target_port_id': conn.target_port_id
                    }
                    for conn in self.connections.values()
                ]
            }
            
            # In a real application, you would save to a file
            # For now, we'll just show the JSON
            self.notification_service.notify_success("Graph data ready for export")
            self.status_message = "Graph saved"
            print(json.dumps(graph_data, indent=2))
            
        except Exception as e:
            self.notification_service.notify_error(f"Error saving graph: {str(e)}")
    
    def load_graph(self):
        """Load a graph from JSON data"""
        # This is a placeholder - in a real app you'd load from a file
        self.notification_service.notify("Load functionality not implemented yet")
        self.status_message = "Load not implemented"
    
    def get_node_at_position(self, x: float, y: float) -> Optional[str]:
        """Get the node at a specific position"""
        for node in self.nodes.values():
            bounds = node.get_bounds()
            if (bounds['left'] <= x <= bounds['right'] and 
                bounds['top'] <= y <= bounds['bottom']):
                return node.id
        return None
        
    def execute_graph(self):
        """Execute the graph (placeholder for actual execution logic)"""
        self.notification_service.notify("Graph execution not implemented yet")
        self.status_message = "Execution not implemented"
```

---
## `utils/NodePanel.py`
---

```python
"""
Node Editor component for individual node rendering and interaction
"""

from typing import Dict, Any
from nicegui import ui, events
from utils.node import Node, NodePort

class NodePanel:
    """Handles rendering and interaction for individual nodes"""
    
    def __init__(self, node: Node, node_graph):
        self.node = node
        self.node_graph = node_graph
        self.ui_element = None
        # Local dragging state
        self._is_dragging = False
        self._drag_offset = (0, 0)
        self._drag_start_pos = (0, 0)
        
    def render(self) -> ui.element:
        """Render the node as a UI element"""
        # Use a card to represent the node
        with ui.card().tight().classes(
            f'absolute node-card node-{self.node.node_type.value}'
        ).style(
            f'left: {self.node.x}px; '
            f'top: {self.node.y}px; '
            f'width: {self.node.width}px; '
            f'min-height: {self.node.height}px; '
            f'background: {self._get_node_color()}; '
            f'border: {"2px solid #1976d2" if self.node.selected else "1px solid #ccc"}; '
            'cursor: grab; '
            'user-select: none; '
            'z-index: 1;'
        ).props(f'data-node-id="{self.node.id}"') as self.node_card:
            
            # Node header with drag handle
            with ui.row().classes('w-full items-center justify-between q-pa-xs drag-handle').style('cursor: grab;'):
                ui.icon('drag_indicator').classes(
                        'text-grey-6'
                    ).on(
                        'mousedown', 
                        self._on_mouse_down, 
                        args=[
                            'clientX', 
                            'clientY', 
                            'offsetX', 
                            'offsetY', 
                            'button'
                        ]
                    )
                ui.label(self.node.name).classes('text-subtitle2 font-weight-bold')
                
                # Close button
                ui.button(
                    icon='close',
                    on_click=lambda: self.node_graph.remove_node(self.node.id)
                ).props('flat dense size=sm').classes('text-red')
            
            ui.separator()
            
            # Node content area
            with ui.row().classes('w-full justify-start q-pa-xs'):
                self._render_node_content()
            
            # Input ports
            if self.node.inputs:
                for port in self.node.inputs:
                    self._render_input_port(port)
            
            # Output ports
            if self.node.outputs:
                for port in self.node.outputs:
                    self._render_output_port(port)
            
            # Add drag and click handlers using NiceGUI's event system
            self.node_card.on('click', self._on_click)
            
            self.ui_element = self.node_card
            
        return self.node_card
    
    def _render_node_content(self):
        """Render node-specific content"""
        # Different content based on node type
        if self.node.node_type.value == 'comment':
            ui.textarea(
                placeholder='Enter comment...',
                value=self.node.properties.get('comment', '')
            ).classes('w-full').props('dense outlined')
            
        elif self.node.node_type.value == 'input':
            with ui.column().classes('w-full'):
                ui.label('Value:').classes('text-caption')
                ui.input(
                    value=str(self.node.properties.get('value', '')),
                    on_change=lambda e: self._update_property('value', e.value)
                ).classes('w-full').props('dense outlined')
                
        elif self.node.node_type.value in ['add', 'subtract', 'multiply', 'divide']:
            ui.label(f'Operation: {self.node.node_type.value.upper()}').classes('text-caption')
            
        elif self.node.node_type.value == 'display':
            result = self.node.properties.get('result', 'No data')
            ui.label(f'Output: {result}').classes('text-caption')
            
        else:
            # Default content
            ui.label(f'Type: {self.node.node_type.value}').classes('text-caption')
    
    def _render_input_port(self, port: NodePort):
        """Render an input port"""
        color = self._get_port_color(port.data_type)
        
        with ui.row().classes('w-full items-center justify-start'):
            # Port connector
            ui.element('div').classes(
                f'port input-port port-{port.data_type}'
            ).style(
                f'width: 12px; height: 12px; '
                f'background: {color}; '
                f'border: 2px solid white; '
                f'border-radius: 50%; '
                f'margin-right: 4px; '
                f'cursor: crosshair;'
            ).props(f'data-port-id="{port.id}"')
            
            # Port label
            ui.label(port.name).classes('text-caption')
    
    def _render_output_port(self, port: NodePort):
        """Render an output port"""
        color = self._get_port_color(port.data_type)
        
        with ui.row().classes('w-full items-center justify-end'):
            # Port label
            ui.label(port.name).classes('text-caption')
            
            # Port connector
            ui.element('div').classes(
                f'port output-port port-{port.data_type}'
            ).style(
                f'width: 12px; height: 12px; '
                f'background: {color}; '
                f'border: 2px solid white; '
                f'border-radius: 50%; '
                f'margin-left: 4px; '
                f'cursor: crosshair;'
            ).props(f'data-port-id="{port.id}"')
    
    def _get_node_color(self) -> str:
        """Get the background color for the node based on its type"""
        colors = {
            'input': '#e8f5e8',
            'output': '#ffe8e8',
            'comment': '#fff8e1',
            'add': '#e3f2fd',
            'subtract': '#e3f2fd', 
            'multiply': '#e3f2fd',
            'divide': '#e3f2fd',
            'and': '#f3e5f5',
            'or': '#f3e5f5',
            'not': '#f3e5f5',
            'compare': '#f3e5f5',
            'display': '#fce4ec',
            'chart': '#fce4ec',
            'export': '#fce4ec'
        }
        return colors.get(self.node.node_type.value, '#f5f5f5')
    
    def _get_port_color(self, data_type: str) -> str:
        """Get the color for a port based on its data type"""
        colors = {
            'number': '#2196f3',
            'string': '#4caf50', 
            'boolean': '#ff9800',
            'array': '#9c27b0',
            'any': '#757575'
        }
        return colors.get(data_type, '#757575')
    
    def _update_property(self, key: str, value: Any):
        """Update a node property"""
        self.node.properties[key] = value
        self.node_graph.update_node_property(self.node.id, key, value)
    
    def _on_mouse_down(self, e):
        """Handle mouse down event to start dragging"""
        # Only handle left mouse button
        if e.args.get('button', 0) != 0:
            return
            
        client_x = e.args.get('clientX', 0)
        client_y = e.args.get('clientY', 0)
        
        # Start local dragging
        self._start_local_drag(client_x, client_y)
        
        # Change cursor to indicate dragging
        self.node_card.style('cursor: grabbing;')
        # Note: Removed direct ui.notify call - notifications should be handled by higher layers

    def _on_click(self, e):
        """Handle node click for selection"""
        # Only select if we're not dragging
        if not self._is_dragging:
            self.node_graph.select_node(self.node.id, multi_select=False)
            # Note: Removed direct ui.notify call - notifications should be handled by higher layers
    
    def update_position(self, x: float, y: float):
        """Update the visual position of the node"""
        self.node.x = x
        self.node.y = y
        # Update the visual position immediately
        if self.node_card:
            self.node_card.style(
                f'left: {self.node.x}px; '
                f'top: {self.node.y}px; '
                f'width: {self.node.width}px; '
                f'min-height: {self.node.height}px; '
                f'background: {self._get_node_color()}; '
                f'border: {"2px solid #1976d2" if self.node.selected else "1px solid #ccc"}; '
                'cursor: grab; '
                'user-select: none; '
                'z-index: 1;'
            )
    
    def update_selection(self):
        """Update the visual selection state"""
        if self.ui_element:
            border_style = "2px solid #1976d2" if self.node.selected else "1px solid #ccc"
            # In a production app, you'd need more sophisticated style management
            pass
    
    # Local dragging methods
    def _start_local_drag(self, client_x: float, client_y: float):
        """Start local dragging"""
        self._is_dragging = True
        self._drag_start_pos = (client_x, client_y)
        self._drag_offset = (client_x - self.node.x, client_y - self.node.y)
        
        # Notify node graph that dragging started
        self.node_graph.on_node_drag_started(self.node.id)
    
    def update_drag_position(self, client_x: float, client_y: float):
        """Update position during drag"""
        if not self._is_dragging:
            return
        
        # Calculate new position
        new_x = client_x - self._drag_offset[0]
        new_y = client_y - self._drag_offset[1]
        
        # Apply constraints (stay within bounds)
        new_x = max(0, new_x)
        new_y = max(0, new_y)
        
        # Update the node model
        self.node.set_position(new_x, new_y)
        
        # Update visual position immediately
        self._update_visual_position()
        
        # Notify node graph of position change
        self.node_graph.on_node_position_changed(self.node.id, new_x, new_y)
    
    def end_local_drag(self):
        """End local dragging"""
        if self._is_dragging:
            self._is_dragging = False
            self._drag_offset = (0, 0)
            self._drag_start_pos = (0, 0)
            
            # Reset cursor
            if self.node_card:
                self.node_card.style('cursor: grab;')
            
            # Notify node graph that dragging ended
            self.node_graph.on_node_drag_ended(self.node.id)
    
    def _update_visual_position(self):
        """Update the visual position of the node"""
        if self.node_card:
            self.node_card.style(
                f'left: {self.node.x}px; '
                f'top: {self.node.y}px; '
                f'width: {self.node.width}px; '
                f'min-height: {self.node.height}px; '
                f'background: {self._get_node_color()}; '
                f'border: {"2px solid #1976d2" if self.node.selected else "1px solid #ccc"}; '
                'cursor: grabbing; '
                'user-select: none; '
                'z-index: 1;'
            )
    
    def is_dragging(self) -> bool:
        """Check if this node is currently being dragged"""
        return self._is_dragging
```

---
## `utils/node.py`
---

```python
"""
Node model definitions for the Node Graph Editor
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from enum import Enum
import uuid

class NodeType(Enum):
    """Enumeration of available node types"""
    INPUT = "input"
    OUTPUT = "output"
    COMMENT = "comment"
    ADD = "add"
    SUBTRACT = "subtract"
    MULTIPLY = "multiply"
    DIVIDE = "divide"
    AND = "and"
    OR = "or"
    NOT = "not"
    COMPARE = "compare"
    DISPLAY = "display"
    CHART = "chart"
    EXPORT = "export"

@dataclass
class NodePort:
    """Represents an input or output port on a node"""
    id: str
    name: str
    data_type: str = "any"
    is_input: bool = True
    connected_to: List[str] = field(default_factory=list)
    value: Any = None

@dataclass
class Node:
    """Represents a node in the graph"""
    id: str
    node_type: NodeType
    name: str
    x: float = 100.0
    y: float = 100.0
    width: float = 150.0
    height: float = 100.0
    inputs: List[NodePort] = field(default_factory=list)
    outputs: List[NodePort] = field(default_factory=list)
    properties: Dict[str, Any] = field(default_factory=dict)
    selected: bool = False
    
    def __post_init__(self):
        """Initialize default ports based on node type"""
        if not self.inputs and not self.outputs:
            self._setup_default_ports()
    
    def _setup_default_ports(self):
        """Setup default input/output ports based on node type"""
        port_configs = {
            NodeType.INPUT: {
                'outputs': [('output', 'any')]
            },
            NodeType.OUTPUT: {
                'inputs': [('input', 'any')]
            },
            NodeType.COMMENT: {
                'inputs': [],
                'outputs': []
            },
            NodeType.ADD: {
                'inputs': [('a', 'number'), ('b', 'number')],
                'outputs': [('result', 'number')]
            },
            NodeType.SUBTRACT: {
                'inputs': [('a', 'number'), ('b', 'number')],
                'outputs': [('result', 'number')]
            },
            NodeType.MULTIPLY: {
                'inputs': [('a', 'number'), ('b', 'number')],
                'outputs': [('result', 'number')]
            },
            NodeType.DIVIDE: {
                'inputs': [('a', 'number'), ('b', 'number')],
                'outputs': [('result', 'number')]
            },
            NodeType.AND: {
                'inputs': [('a', 'boolean'), ('b', 'boolean')],
                'outputs': [('result', 'boolean')]
            },
            NodeType.OR: {
                'inputs': [('a', 'boolean'), ('b', 'boolean')],
                'outputs': [('result', 'boolean')]
            },
            NodeType.NOT: {
                'inputs': [('input', 'boolean')],
                'outputs': [('result', 'boolean')]
            },
            NodeType.COMPARE: {
                'inputs': [('a', 'any'), ('b', 'any')],
                'outputs': [('result', 'boolean')]
            },
            NodeType.DISPLAY: {
                'inputs': [('input', 'any')],
                'outputs': []
            },
            NodeType.CHART: {
                'inputs': [('data', 'array')],
                'outputs': []
            },
            NodeType.EXPORT: {
                'inputs': [('data', 'any')],
                'outputs': []
            }
        }
        
        config = port_configs.get(self.node_type, {'inputs': [], 'outputs': []})
        
        # Create input ports
        for port_name, data_type in config.get('inputs', []):
            port_id = f"{self.id}_{port_name}_in"
            self.inputs.append(NodePort(
                id=port_id,
                name=port_name,
                data_type=data_type,
                is_input=True
            ))
        
        # Create output ports
        for port_name, data_type in config.get('outputs', []):
            port_id = f"{self.id}_{port_name}_out"
            self.outputs.append(NodePort(
                id=port_id,
                name=port_name,
                data_type=data_type,
                is_input=False
            ))
    
    @classmethod
    def create(cls, node_type: NodeType, name: str, x: float = 100, y: float = 100) -> 'Node':
        """Factory method to create a new node"""
        node_id = str(uuid.uuid4())
        return cls(
            id=node_id,
            node_type=node_type,
            name=name,
            x=x,
            y=y
        )
    
    def get_input_port(self, name: str) -> Optional[NodePort]:
        """Get input port by name"""
        for port in self.inputs:
            if port.name == name:
                return port
        return None
    
    def get_output_port(self, name: str) -> Optional[NodePort]:
        """Get output port by name"""
        for port in self.outputs:
            if port.name == name:
                return port
        return None
    
    def set_position(self, x: float, y: float):
        """Update node position"""
        self.x = x
        self.y = y
    
    def get_bounds(self) -> Dict[str, float]:
        """Get node bounding box"""
        return {
            'left': self.x,
            'top': self.y,
            'right': self.x + self.width,
            'bottom': self.y + self.height
        }

@dataclass
class Connection:
    """Represents a connection between two node ports"""
    id: str
    source_port_id: str
    target_port_id: str
    
    @classmethod
    def create(cls, source_port_id: str, target_port_id: str) -> 'Connection':
        """Factory method to create a new connection"""
        connection_id = str(uuid.uuid4())
        return cls(
            id=connection_id,
            source_port_id=source_port_id,
            target_port_id=target_port_id
        )
```

---
## `main.py`
---

```python
#!/usr/bin/env python3
"""
Simple Node Graph Editor built with NiceGUI and Quasar
"""
from nicegui import ui, app

from utils.NodePanel import NodePanel
from utils.NodeCanvas import NodeCanvas
from utils.node import Node, NodeType
from utils.Graph import GraphManager

try:
    from services.nicegui_notification_service import NiceGUINotificationService
    NICEGUI_AVAILABLE = True
except ImportError:
    from services.nicegui_notification_service import ConsoleNotificationService
    NICEGUI_AVAILABLE = False

def main():
    """Main application entry point"""
    
    # Add custom CSS and JavaScript for enhanced functionality
    ui.add_head_html('''
        <style>
            .draggable-node {
                transition: none !important;
            }
            .draggable-node:active {
                cursor: grabbing !important;
                z-index: 1000 !important;
            }
            .draggable-node.dragging {
                box-shadow: 0 8px 16px rgba(0,0,0,0.3) !important;
                transform: rotate(2deg);
            }
        </style>

    ''')
    
    # Initialize the notification service and graph manager
    if NICEGUI_AVAILABLE:
        notification_service = NiceGUINotificationService()
    else:
        notification_service = ConsoleNotificationService()
    
    graph_manager = GraphManager(notification_service)
    
    # Add API endpoint for position updates
    from nicegui import app
    from starlette.requests import Request
    import json
    
     
    # Create the main layout
    with ui.header(elevated=True).style('background-color: #1976d2'):
        ui.label('Node Graph Editor').style('font-size: 1.5rem; font-weight: bold; color: white')
        ui.space()
        with ui.row():
            ui.button('New Graph', icon='add', on_click=lambda: graph_manager.clear_graph()).props('flat color=white')
            ui.button('Save Graph', icon='save', on_click=lambda: graph_manager.save_graph()).props('flat color=white')
            ui.button('Load Graph', icon='folder_open', on_click=lambda: graph_manager.load_graph()).props('flat color=white')
    
    # Create the main container
    with ui.splitter(value=20).classes('w-full h-screen') as splitter:
        # Left panel - Node palette
        with splitter.before:
            with ui.card().tight().classes('h-full'):
                ui.label('Node Palette').classes('text-h6 q-pa-md')
                ui.separator()
                
                # Node categories
                with ui.expansion('Basic Nodes', icon='category').classes('w-full'):
                    create_node_palette_section(graph_manager, 'basic')
                
                with ui.expansion('Math Nodes', icon='calculate').classes('w-full'):
                    create_node_palette_section(graph_manager, 'math')
                
                with ui.expansion('Logic Nodes', icon='psychology').classes('w-full'):
                    create_node_palette_section(graph_manager, 'logic')
                
                with ui.expansion('Output Nodes', icon='output').classes('w-full'):
                    create_node_palette_section(graph_manager, 'output')
        
        # Right panel - Node graph canvas
        with splitter.after:
            node_graph = NodeCanvas(graph_manager)
            node_graph.render()
    
    # Add keyboard controls for selected nodes (simplified)
    def handle_keyboard(e):
        """Handle keyboard events for moving selected nodes"""
        if graph_manager.selected_nodes:
            step = 10  # pixels to move
            for node_id in graph_manager.selected_nodes:
                node = graph_manager.nodes.get(node_id)
                if node:
                    if e.key.name == 'ARROW_UP':
                        graph_manager.move_node(node_id, node.x, max(0, node.y - step))
                    elif e.key.name == 'ARROW_DOWN':
                        graph_manager.move_node(node_id, node.x, node.y + step)
                    elif e.key.name == 'ARROW_LEFT':
                        graph_manager.move_node(node_id, max(0, node.x - step), node.y)
                    elif e.key.name == 'ARROW_RIGHT':
                        graph_manager.move_node(node_id, node.x + step, node.y)
    
    # Try to add global keyboard handler (may not work in all NiceGUI versions)
    try:
        ui.keyboard(handle_keyboard, active=True)
    except Exception as e:
        print(f"Keyboard handler not available: {e}")
    
    # Bottom status bar
    with ui.footer().style('background-color: #f5f5f5; border-top: 1px solid #ddd'):
        with ui.row().classes('w-full justify-between items-center q-pa-sm'):
            ui.label('Ready').bind_text_from(graph_manager, 'status_message')
            ui.label().bind_text_from(graph_manager, 'node_count', 
                                      backward=lambda count: f'Nodes: {count}')

def create_node_palette_section(graph_manager: GraphManager, category: str):
    """Create a section of the node palette for a specific category"""
    
    node_types = {
        'basic': [
            ('Input', 'input', 'keyboard'),
            ('Output', 'output', 'output'),
            ('Comment', 'comment', 'comment'),
        ],
        'math': [
            ('Add', 'add', 'add'),
            ('Subtract', 'subtract', 'remove'),
            ('Multiply', 'multiply', 'close'),
            ('Divide', 'divide', 'horizontal_rule'),
        ],
        'logic': [
            ('AND', 'and', 'logic'),
            ('OR', 'or', 'logic'),
            ('NOT', 'not', 'not_interested'),
            ('Compare', 'compare', 'compare_arrows'),
        ],
        'output': [
            ('Display', 'display', 'monitor'),
            ('Chart', 'chart', 'bar_chart'),
            ('Export', 'export', 'file_download'),
        ]
    }
    
    if category in node_types:
        for name, node_type, icon in node_types[category]:
            ui.button(
                name, 
                icon=icon, 
                on_click=lambda t=node_type, n=name: graph_manager.add_node_from_palette(t, n)
            ).props('flat full-width align=left').classes('q-ma-xs')

if __name__ in {'__main__', '__mp_main__'}:
    main()
    ui.run(
        title='Node Graph Editor',
        favicon='🔗',
        dark=False,
        show=True,
        reload=True,
        port=8080
    )
```

---
## `controllers/ToolbarController.py`
---

```python
"""
Controller for graph toolbar operations
"""

from typing import TYPE_CHECKING
from nicegui import ui

if TYPE_CHECKING:
    from utils.Graph import GraphManager
    from utils.NodeCanvas import NodeCanvas


class ToolbarController:
    """Handles toolbar UI and operations"""
    
    def __init__(self, graph_manager: 'GraphManager', node_graph: 'NodeCanvas'):
        self.graph_manager = graph_manager
        self.node_graph = node_graph
    
    def render_toolbar(self):
        """Render the toolbar UI"""
        with ui.row().classes('w-full justify-between items-center q-pa-sm'):
            with ui.row():
                ui.button('Fit to Screen', icon='fit_screen', 
                         on_click=self._fit_to_screen).props('outline')
                ui.button('Center Graph', icon='center_focus_strong',
                         on_click=self._center_graph).props('outline')
                ui.button('Execute', icon='play_arrow',
                         on_click=self._execute_graph).props('color=green')
            
            with ui.row():
                ui.label('Zoom: 100%').classes('text-caption')
                ui.button('Reset View', icon='refresh',
                         on_click=self._reset_view).props('flat')
    
    def _fit_to_screen(self):
        """Fit all nodes to the screen"""
        # This would implement actual fit-to-screen logic
        self.graph_manager.notification_service.notify("Fit to screen not implemented yet")
    
    def _center_graph(self):
        """Center the graph view"""
        # This would implement actual centering logic
        self.graph_manager.notification_service.notify("Center graph not implemented yet")
    
    def _execute_graph(self):
        """Execute the graph"""
        self.graph_manager.execute_graph()
    
    def _reset_view(self):
        """Reset the view to default zoom and position"""
        # This would implement actual view reset logic
        self.graph_manager.notification_service.notify("Reset view not implemented yet")
```

---
## `controllers/__init__.py`
---

```python
"""
Controllers package
"""

from .ToolbarController import ToolbarController

__all__ = ['ToolbarController']
```

---
## `services/notification_service.py`
---

```python
"""
Service interfaces for decoupling business logic from UI framework
"""

from abc import ABC, abstractmethod
from typing import Optional

class NotificationService(ABC):
    """Abstract interface for notification services"""
    
    @abstractmethod
    def notify(self, message: str, level: str = 'info', duration: Optional[float] = None):
        """
        Send a notification to the user
        
        Args:
            message: The notification message
            level: The notification level ('info', 'success', 'warning', 'error')
            duration: Optional duration in seconds (None for default)
        """
        pass
    
    @abstractmethod
    def notify_success(self, message: str):
        """Send a success notification"""
        pass
    
    @abstractmethod
    def notify_error(self, message: str):
        """Send an error notification"""
        pass
    
    @abstractmethod
    def notify_warning(self, message: str):
        """Send a warning notification"""
        pass


class NullNotificationService(NotificationService):
    """Null object implementation for testing"""
    
    def notify(self, message: str, level: str = 'info', duration: Optional[float] = None):
        pass
    
    def notify_success(self, message: str):
        pass
    
    def notify_error(self, message: str):
        pass
    
    def notify_warning(self, message: str):
        pass
```

---
## `services/nicegui_notification_service.py`
---

```python
"""
NiceGUI implementation of the notification service
"""

from typing import Optional
from services.notification_service import NotificationService

try:
    from nicegui import ui
    NICEGUI_AVAILABLE = True
except ImportError:
    NICEGUI_AVAILABLE = False


class NiceGUINotificationService(NotificationService):
    """NiceGUI implementation of notification service"""
    
    def __init__(self):
        if not NICEGUI_AVAILABLE:
            raise ImportError("NiceGUI is required for NiceGUINotificationService")
    
    def notify(self, message: str, level: str = 'info', duration: Optional[float] = None):
        """Send a notification using NiceGUI"""
        # Map our level names to NiceGUI types
        level_mapping = {
            'info': 'info',
            'success': 'positive', 
            'warning': 'warning',
            'error': 'negative'
        }
        
        nicegui_type = level_mapping.get(level, 'info')
        
        if duration is not None:
            ui.notify(message, type=nicegui_type, timeout=duration)
        else:
            ui.notify(message, type=nicegui_type)
    
    def notify_success(self, message: str):
        """Send a success notification"""
        self.notify(message, 'success')
    
    def notify_error(self, message: str):
        """Send an error notification"""
        self.notify(message, 'error')
    
    def notify_warning(self, message: str):
        """Send a warning notification"""
        self.notify(message, 'warning')


class ConsoleNotificationService(NotificationService):
    """Console-based implementation for testing/debugging"""
    
    def notify(self, message: str, level: str = 'info', duration: Optional[float] = None):
        """Print notification to console"""
        print(f"[{level.upper()}] {message}")
    
    def notify_success(self, message: str):
        """Print success notification to console"""
        self.notify(message, 'success')
    
    def notify_error(self, message: str):
        """Print error notification to console"""
        self.notify(message, 'error')
    
    def notify_warning(self, message: str):
        """Print warning notification to console"""
        self.notify(message, 'warning')
```

---
## `services/__init__.py`
---

```python
# Services package
from .notification_service import NotificationService, NullNotificationService
from .nicegui_notification_service import NiceGUINotificationService, ConsoleNotificationService

__all__ = [
    'NotificationService',
    'NullNotificationService', 
    'NiceGUINotificationService',
    'ConsoleNotificationService'
]
```

