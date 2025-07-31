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
