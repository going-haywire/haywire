"""
GraphCanvasVue - Vue-based graph canvas component for NiceGUI

This component provides a clean Python wrapper around a Vue component that handles
all client-side graph canvas interactions with the enhanced event system.

ENHANCED VERSION: Now uses unified event handling with type-safe event classes.
"""

from typing import Dict, List, Optional, Callable
import uuid
import json
from pathlib import Path

from nicegui import ui, events
from nicegui.dependencies import register_library

from haywire.ui.utils import generate_connection_id
from .event_definitions import BaseGraphEvent, GRAPH_EVENT_REGISTRY

# Get relative path from current working directory
# This is the only way to make the generated library work with NiceGUI
# using a simple import statement withing the Vue component won't work
script_dir = Path(__file__).parent
library_path = script_dir / "generated" / "graph_events.js"

if library_path.exists():
    try:
        my_library = register_library(library_path, max_time=library_path.stat().st_mtime)
    except Exception as e:
        print(f"❌ Failed to register library: {e}")
else:
    print(f"❌ Library not found at relative path either: {library_path}")


class GraphCanvasVue(ui.element, component='graph_canvas.vue'):
    """Vue-based graph canvas component with enhanced event handling."""
    
    def __init__(self, 
                 on_canvas_event: Optional[Callable[[BaseGraphEvent], None]] = None,
                 zoom_container=None,
                 canvas_width: int = 8000, 
                 canvas_height: int = 8000):
        super().__init__()
        self.libraries.append(my_library)

        # Single unified event callback
        self._on_canvas_event = on_canvas_event
        
        # Store zoom container reference
        self.zoom_container = zoom_container
        
        # Props for Vue component  
        self._props['canvasWidth'] = canvas_width
        self._props['canvasHeight'] = canvas_height
        self._props['connections'] = []
        self._props['data-graph_canvas'] = True
        
        # Register single unified event handler
        self.on('canvasEvent', self._handle_canvas_event)
    
    def _handle_canvas_event(self, event_data):
        """
        Unified canvas event handler - routes to GraphCanvasManager
        """
        if self._on_canvas_event and hasattr(event_data, 'args'):
            event = event_data.args
            event_type = event.get('event_type')
            
            # Log for debugging
            print(f"🔄 Vue→Python Event: {event_type} | Data: {event.get('data', {})}")
            
            # Create event instance from registry
            if event_type in GRAPH_EVENT_REGISTRY:
                event_class = GRAPH_EVENT_REGISTRY[event_type]
                try:
                    event_instance = event_class.from_dict(event)
                    self._on_canvas_event(event_instance)
                except Exception as e:
                    print(f"Error creating event instance for {event_type}: {e}")
                    # Fallback to raw dict for backward compatibility
                    self._on_canvas_event(event)
            else:
                print(f"Unknown event type: {event_type}")
                self._on_canvas_event(event)
    
    def emit_sync_event(self, event: BaseGraphEvent):
        """
        Send sync event to Vue component
        """
        event_dict = event.to_dict()
        event_type = event_dict.get('event_type')
        data = event_dict.get('data', {})
        
        print(f"🔄 Python→Vue Event: {event_type} | Data: {data}")
        
        # Send to Vue component
        self.run_method('handleSyncEvent', event_dict)
    
  # =============================================================================
    # BACKWARD COMPATIBILITY METHODS
    # These methods maintain compatibility with existing code during migration
    # =============================================================================
    
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
        
    def cleanup(self):
        """Cleanup resources and references."""
        # Clear callbacks
        self._on_canvas_event = None
        self.zoom_container = None

