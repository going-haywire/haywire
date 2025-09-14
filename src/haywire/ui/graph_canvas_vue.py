"""
GraphCanvasVue - Vue-based graph canvas component for NiceGUI

This component provides a clean Python wrapper around a Vue component that handles
all client-side graph canvas interactions including:
- Connection creation & drop
- SVG path rendering and updates
- Node position change detection
- Zoom/pan coordinate transformations
- Event emission to Python callbacks

The Vue component handles all JavaScript logic while this Python wrapper provides
a clean interface that integrates with the existing GraphCanvasManager API.
"""

from nicegui import ui, events
from typing import Dict, List, Optional, Callable
import uuid
import json

from haywire.ui.utils import generate_connection_id


class GraphCanvasVue(ui.element, component='graph_canvas.vue'):
    """Vue-based graph canvas component with event handling."""
    
    def __init__(self, on_node_created=None, on_connection_created=None, 
                 on_connection_removed=None, on_node_position_changed=None,
                 on_connection_clicked=None, zoom_container=None,
                 on_node_drag_start=None, on_node_drag_end=None,
                 on_selection_changed=None,
                 on_context_menu_canvas=None, on_context_menu_node=None,
                 on_context_menu_connection=None,
                 canvas_width: int = 8000, canvas_height: int = 8000):
        super().__init__()
        
        # Store callbacks
        self._on_node_created = on_node_created
        self._on_connection_created = on_connection_created
        self._on_connection_removed = on_connection_removed
        self._on_node_position_changed = on_node_position_changed
        self._on_connection_clicked = on_connection_clicked
        self._on_node_drag_start = on_node_drag_start
        self._on_node_drag_end = on_node_drag_end
        self._on_selection_changed = on_selection_changed
        self._on_context_menu_canvas = on_context_menu_canvas
        self._on_context_menu_node = on_context_menu_node
        self._on_context_menu_connection = on_context_menu_connection
        
        # Store zoom container reference if provided
        self.zoom_container = zoom_container
        
        # Props for Vue component
        self._props['canvasWidth'] = canvas_width
        self._props['canvasHeight'] = canvas_height
        self._props['connections'] = []  # Initialize empty connections list
        
        # Note: zoomState prop removed - zoom/pan is handled by CSS transforms in parent container
        
        # Add unique identifier for JS selection
        self._props['data-graph_canvas'] = True
        
        # Setup event handlers for Vue component events
        self.on('nodeCreated', self._handle_node_created)
        self.on('connectionCreated', self._handle_connection_created)
        self.on('connectionRemoved', self._handle_connection_removed)
        self.on('connectionClicked', self._handle_connection_clicked)
        self.on('nodePositionChanged', self._handle_node_position_changed)
        self.on('nodeDragStart', self._handle_node_drag_start)
        self.on('nodeDragEnd', self._handle_node_drag_end)
        self.on('selectionChanged', self._handle_selection_changed)
        self.on('contextMenuCanvas', self._handle_context_menu_canvas)
        self.on('contextMenuNode', self._handle_context_menu_node)
        self.on('contextMenuConnection', self._handle_context_menu_connection)
    
    def _handle_node_created(self, event_data):
        """Handle node creation event from Vue component."""
        if self._on_node_created:
            # Extract position from event data
            position = event_data.args.get('position', {})
            x = position.get('x', 0)
            y = position.get('y', 0)
            self._on_node_created(x, y)
    
    def _handle_connection_created(self, event_data):
        """Handle connection creation event from Vue component."""
        print(f"[GraphCanvasVue] Connection created event: {event_data}")
        if self._on_connection_created:
            args = event_data.args
            start_node_id = args.get('startNodeId')
            start_port = args.get('startPort')
            end_node_id = args.get('endNodeId')
            end_port = args.get('endPort')
            
            print(f"[GraphCanvasVue] Parsed connection args: startNodeId={start_node_id}, startPort={start_port}, endNodeId={end_node_id}, endPort={end_port}")
            
            if start_node_id and start_port and end_node_id and end_port:
                print(f"[GraphCanvasVue] Calling connection created callback with: {start_node_id}:{start_port} -> {end_node_id}:{end_port}")
                self._on_connection_created(start_node_id, start_port, end_node_id, end_port)
            else:
                print(f"[GraphCanvasVue] Warning: Missing required connection arguments in event: {args}")
    
    def _handle_connection_removed(self, event_data):
        """Handle connection removal event from Vue component."""
        print(f"[GraphCanvasVue] Connection removed event: {event_data}")
        if self._on_connection_removed:
            connection_id = event_data.args.get('connectionId')
            if connection_id:
                self._on_connection_removed(connection_id)
    
    def _handle_connection_clicked(self, event_data):
        """Handle connection click event from Vue component."""
        print(f"[GraphCanvasVue] Connection clicked event: {event_data}")
        if self._on_connection_clicked:
            connection_id = event_data.args.get('connectionId')
            if connection_id:
                self._on_connection_clicked(connection_id)
    
    def _handle_node_position_changed(self, event_data):
        """Handle node position change event from Vue component."""
        if self._on_node_position_changed:
            args = event_data.args
            node_id = args.get('nodeId')
            # Vue emits x and y directly, not nested in a position object
            x = args.get('x', 0)
            y = args.get('y', 0)
            
            if node_id is not None:
                print(f"[GraphCanvasVue] Node position changed: {node_id} -> ({x}, {y})")
                self._on_node_position_changed(node_id, x, y)  # Pass x, y as separate args
            else:
                print(f"[GraphCanvasVue] Warning: nodeId is missing in position change event: {args}")
    
    def _handle_node_drag_start(self, event_data):
        """Handle node drag start event from Vue component."""
        if self._on_node_drag_start:
            args = event_data.args
            node_id = args.get('nodeId')
            
            if node_id is not None:
                print(f"[GraphCanvasVue] Node drag started: {node_id}")
                self._on_node_drag_start(node_id)
            else:
                print(f"[GraphCanvasVue] Warning: nodeId is missing in drag start event: {args}")
    
    def _handle_node_drag_end(self, event_data):
        """Handle node drag end event from Vue component."""
        if self._on_node_drag_end:
            args = event_data.args
            node_id = args.get('nodeId')
            position_changed = args.get('positionChanged', True)
            
            if node_id is not None:
                print(f"[GraphCanvasVue] Node drag ended: {node_id}, position changed: {position_changed}")
                self._on_node_drag_end(node_id, position_changed)
            else:
                print(f"[GraphCanvasVue] Warning: nodeId is missing in drag end event: {args}")
    
    def _handle_selection_changed(self, event_data):
        """Handle selection change event from Vue component."""
        if self._on_selection_changed:
            args = event_data.args
            selected_nodes = args.get('selectedNodes', [])
            selected_connections = args.get('selectedConnections', [])
            
            print(f"[GraphCanvasVue] Selection changed: nodes={selected_nodes}, connections={selected_connections}")
            self._on_selection_changed(selected_nodes, selected_connections)
    
    def _handle_context_menu_canvas(self, event_data):
        """Handle canvas context menu event from Vue component."""
        if self._on_context_menu_canvas:
            args = event_data.args
            screen_x = args.get('screenX', 0)
            screen_y = args.get('screenY', 0)
            canvas_x = args.get('canvasX', 0)
            canvas_y = args.get('canvasY', 0)
            
            print(f"[GraphCanvasVue] Canvas context menu: screen({screen_x}, {screen_y}) canvas({canvas_x}, {canvas_y})")
            self._on_context_menu_canvas(screen_x, screen_y, canvas_x, canvas_y)
    
    def _handle_context_menu_node(self, event_data):
        """Handle node context menu event from Vue component."""
        if self._on_context_menu_node:
            args = event_data.args
            node_id = args.get('nodeId')
            x = args.get('x', 0)
            y = args.get('y', 0)
            
            if node_id:
                print(f"[GraphCanvasVue] Node context menu: {node_id} at ({x}, {y})")
                self._on_context_menu_node(node_id, x, y)
    
    def _handle_context_menu_connection(self, event_data):
        """Handle connection context menu event from Vue component."""
        if self._on_context_menu_connection:
            args = event_data.args
            connection_id = args.get('connectionId')
            x = args.get('x', 0)
            y = args.get('y', 0)
            
            if connection_id:
                print(f"[GraphCanvasVue] Connection context menu: {connection_id} at ({x}, {y})")
                self._on_context_menu_connection(connection_id, x, y)
    
    # Connection Management Methods
    
    def add_connection_visual(self, connection_id: str, from_pin_id: str, to_pin_id: str):
        """Add visual connection between pins."""
        print(f"[GraphCanvasVue] add_connection_visual: {connection_id} from {from_pin_id} to {to_pin_id}")
        
        # Parse pin IDs to extract node and port information
        # Expected format: node_id:port_id
        try:
            from_parts = from_pin_id.split(':')
            to_parts = to_pin_id.split(':')
            
            if len(from_parts) == 2 and len(to_parts) == 2:
                output_node_id, outlet_pin_id = from_parts
                input_node_id, inlet_pin_id = to_parts
                
                # Create connection data
                connection_data = {
                    'id': connection_id,
                    'outputNodeId': output_node_id,
                    'outletPinId': outlet_pin_id,
                    'inputNodeId': input_node_id,
                    'inletPinId': inlet_pin_id
                }
                
                # Add to connections prop
                current_connections = list(self._props.get('connections', []))
                # Remove existing connection with same ID if it exists
                current_connections = [c for c in current_connections if c.get('id') != connection_id]
                # Add new connection
                current_connections.append(connection_data)
                # Update the prop
                self._props['connections'] = current_connections
                
                print(f"[GraphCanvasVue] ✅ Connection added to props: {connection_id}")
                return True
            else:
                print(f"[GraphCanvasVue] Invalid pin ID format: {from_pin_id}, {to_pin_id}")
                return False
        except Exception as e:
            print(f"[GraphCanvasVue] Error parsing pin IDs: {e}")
            return False
    
    def remove_connection_visual(self, connection_id: str):
        """Remove visual connection."""
        print(f"[GraphCanvasVue] remove_connection_visual: {connection_id}")
        
        # Remove from connections prop
        current_connections = list(self._props.get('connections', []))
        # Filter out the connection with matching ID
        updated_connections = [c for c in current_connections if c.get('id') != connection_id]
        # Update the prop
        self._props['connections'] = updated_connections
        
        print(f"[GraphCanvasVue] ✅ Connection removed from props: {connection_id}")
        return len(updated_connections) < len(current_connections)  # Return True if connection was found and removed

    def sync_connections_from_edges(self, edges):
        """Sync all connections from a list of edges."""
        print(f"[GraphCanvasVue] sync_connections_from_edges: {len(edges)} edges")
        
        # Convert edges to connection data format
        connection_data_list = []
        for edge in edges:
            # Generate connection ID using Format 2 (consistent with canvas manager)
            connection_id = generate_connection_id(
                edge.output_node_id,
                edge.outlet_pin_id, 
                edge.input_node_id,
                edge.inlet_pin_id
            )
            
            connection_data = {
                'id': connection_id,
                'outputNodeId': edge.output_node_id,
                'outletPinId': edge.outlet_pin_id,
                'inputNodeId': edge.input_node_id,
                'inletPinId': edge.inlet_pin_id
            }
            connection_data_list.append(connection_data)
        
        # Update the connections prop (this will trigger the Vue watcher)
        self._props['connections'] = connection_data_list
        print(f"[GraphCanvasVue] ✅ Connections prop updated with {len(connection_data_list)} connections")
        # print(f"[GraphCanvasVue] Connection data: {connection_data_list}")
        
        # Force a prop update by calling update() on the element
        self.update()
    
    def update_connections_for_node(self, node_id: str):
        """Update all connections for a specific node."""
        # This will trigger the Vue component to refresh connection positions
        # for the specified node by calling the client-side JavaScript
        self.run_method('updateConnectionsForNode', node_id)
    
    def add_node_observer(self, node_id: str):
        """Add mutation/hover observers for a node."""
        self.run_method('addNodeObserver', node_id)
    
    def remove_node_observer(self, node_id: str):
        """Remove observers for a node."""
        self.run_method('removeNodeObserver', node_id)
    
    # Selection Management Methods
    
    def select_node(self, node_id: str, multi_select: bool = False):
        """Select a node in the Vue component."""
        self.run_method('selectNode', node_id, multi_select)
    
    def deselect_node(self, node_id: str):
        """Deselect a node in the Vue component."""
        self.run_method('deselectNode', node_id)
    
    def select_connection(self, connection_id: str, multi_select: bool = False):
        """Select a connection in the Vue component."""
        self.run_method('selectConnection', connection_id, multi_select)
    
    def deselect_connection(self, connection_id: str):
        """Deselect a connection in the Vue component."""
        self.run_method('deselectConnection', connection_id)
    
    def clear_selection(self):
        """Clear all selections in the Vue component."""
        self.run_method('clearSelection')
        
    # Note: sync_zoom_pan_state removed - zoom/pan is handled by CSS transforms
    # in the zoom container, so no need to sync state or trigger connection updates
    
    def cleanup(self):
        """Cleanup resources and references."""
        # Clear callbacks
        self._on_node_created = None
        self._on_connection_created = None
        self._on_connection_removed = None
        self._on_node_position_changed = None
        self._on_connection_clicked = None
        self._on_node_drag_start = None
        self._on_node_drag_end = None
        self.zoom_container = None
        
