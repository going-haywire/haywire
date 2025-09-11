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
from typing import Dict, List, Optional, Tuple, Callable
import uuid
import json


class GraphCanvasVue(ui.element, component='graph_canvas.vue'):
    """Vue-based graph canvas component with event handling."""
    
    def __init__(self, on_node_created=None, on_connection_created=None, 
                 on_connection_removed=None, on_node_position_changed=None,
                 on_connection_clicked=None, zoom_container=None,
                 canvas_width: int = 8000, canvas_height: int = 8000):
        super().__init__()
        
        # Store callbacks
        self._on_node_created = on_node_created
        self._on_connection_created = on_connection_created
        self._on_connection_removed = on_connection_removed
        self._on_node_position_changed = on_node_position_changed
        self._on_connection_clicked = on_connection_clicked
        
        # Store zoom container reference if provided
        self.zoom_container = zoom_container
        
        # Props for Vue component
        self._props['canvasWidth'] = canvas_width
        self._props['canvasHeight'] = canvas_height
        
        # Note: zoomState prop removed - zoom/pan is handled by CSS transforms in parent container
        
        # Add unique identifier for JS selection
        self._props['data-graph_canvas'] = True
        
        # Setup event handlers for Vue component events
        self.on('nodeCreated', self._handle_node_created)
        self.on('connectionCreated', self._handle_connection_created)
        self.on('connectionRemoved', self._handle_connection_removed)
        self.on('connectionClicked', self._handle_connection_clicked)
        self.on('nodePositionChanged', self._handle_node_position_changed)
    
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
            
            if start_node_id and start_port and end_node_id and end_port:
                print(f"[GraphCanvasVue] Calling connection created callback with: {start_node_id}:{start_port} -> {end_node_id}:{end_port}")
                self._on_connection_created(start_node_id, start_port, end_node_id, end_port)
    
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
            position = args.get('position', {})
            x = position.get('x', 0)
            y = position.get('y', 0)
            
            if node_id:
                self._on_node_position_changed(node_id, x, y)
    
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
                
                # Call Vue component method via JavaScript injection
                ui.run_javascript(f"""
                const canvasEl = document.querySelector('[data-graph_canvas]');
                if (canvasEl && canvasEl._graphCanvasControls) {{
                    console.log('[GraphCanvasVue] Calling addConnectionVisual with:', {{
                        outputNodeId: '{output_node_id}',
                        outletPinId: '{outlet_pin_id}',
                        inputNodeId: '{input_node_id}',
                        inletPinId: '{inlet_pin_id}'
                    }});
                    canvasEl._graphCanvasControls.addConnectionVisual({{
                        outputNodeId: '{output_node_id}',
                        outletPinId: '{outlet_pin_id}',
                        inputNodeId: '{input_node_id}',
                        inletPinId: '{inlet_pin_id}'
                    }});
                }} else {{
                    console.error('[GraphCanvasVue] Canvas element or controls not found');
                }}
                """)
            else:
                print(f"[GraphCanvasVue] Invalid pin ID format: {from_pin_id}, {to_pin_id}")
        except Exception as e:
            print(f"[GraphCanvasVue] Error parsing pin IDs: {e}")
    
    def remove_connection_visual(self, connection_id: str):
        """Remove visual connection."""
        print(f"[GraphCanvasVue] remove_connection_visual: {connection_id}")
        
        # Call Vue component method via JavaScript injection
        ui.run_javascript(f"""
        const canvasEl = document.querySelector('[data-graph_canvas]');
        if (canvasEl && canvasEl._graphCanvasControls) {{
            console.log('[GraphCanvasVue] Calling removeConnectionVisual with connectionId:', '{connection_id}');
            canvasEl._graphCanvasControls.removeConnectionVisual('{connection_id}');
        }} else {{
            console.error('[GraphCanvasVue] Canvas element or controls not found');
        }}
        """)
    
    def update_connection_path(self, path_id: str):
        """Update a specific connection path."""
        ui.run_javascript(f"""
        const canvasEl = document.querySelector('[data-graph_canvas]');
        if (canvasEl && canvasEl._graphCanvasControls) {{
            canvasEl._graphCanvasControls.updateConnectionPath('{path_id}');
        }}
        """)
    
    def update_all_connections(self):
        """Update all connection paths (throttled)."""
        ui.run_javascript("""
        const canvasEl = document.querySelector('[data-graph_canvas]');
        if (canvasEl && canvasEl._graphCanvasControls) {
            canvasEl._graphCanvasControls.updateAllConnections();
        }
        """)
    
    def update_connections_for_node(self, node_id: str):
        """Update all connections for a specific node."""
        ui.run_javascript(f"""
        const canvasEl = document.querySelector('[data-graph_canvas]');
        if (canvasEl && canvasEl._graphCanvasControls) {{
            canvasEl._graphCanvasControls.updateConnectionsForNode('{node_id}');
        }}
        """)

    def add_node_observer(self, node_id: str):
        """Add mutation/hover observers for a node."""
        ui.run_javascript(f"""
        const canvasEl = document.querySelector('[data-graph_canvas]');
        if (canvasEl && canvasEl._graphCanvasControls) {{
            canvasEl._graphCanvasControls.addNodeObserver('{node_id}');
        }}
        """)
    
    def remove_node_observer(self, node_id: str):
        """Remove observers for a node."""
        ui.run_javascript(f"""
        const canvasEl = document.querySelector('[data-graph_canvas]');
        if (canvasEl && canvasEl._graphCanvasControls) {{
            canvasEl._graphCanvasControls.removeNodeObserver('{node_id}');
        }}
        """)
    
    def get_pin_position(self, pin_id: str) -> dict:
        """Get the position of a connection pin."""
        # For methods that return values, we'll need to implement via JS callback
        # For now, return empty dict - this would need to be implemented differently
        # if actual return values are needed
        print(f"[GraphCanvasVue] get_pin_position called for pin {pin_id}")
        return {}
    
    def transform_screen_to_svg(self, client_x: float, client_y: float) -> dict:
        """Transform screen coordinates to SVG coordinates."""
        # For methods that return values, we'll need to implement via JS callback
        # For now, return empty dict - this would need to be implemented differently
        # if actual return values are needed  
        print(f"[GraphCanvasVue] transform_screen_to_svg called for ({client_x}, {client_y})")
        return {}
    
    # Convenience Methods
    
    def clear_canvas(self):
        """Clear all connections and reset canvas state."""
        ui.run_javascript("""
        const canvasEl = document.querySelector('[data-graph_canvas]');
        if (canvasEl && canvasEl._graphCanvasControls) {
            canvasEl._graphCanvasControls.clearAllConnections();
        }
        """)
    
    def get_canvas_size(self) -> Tuple[int, int]:
        """Get canvas dimensions."""
        return (self._props['canvasWidth'], self._props['canvasHeight'])
    
    def set_canvas_size(self, width: int, height: int):
        """Update canvas size."""
        self._props['canvasWidth'] = width
        self._props['canvasHeight'] = height
        self.update()
        
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
        self.zoom_container = None
        
