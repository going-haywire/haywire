"""
ContextMenu - Vue-based context menu component for NiceGUI

This component provides context menus for different elements in the graph canvas:
- Canvas: Node creation menu when Ctrl+clicking on empty space
- Nodes: Node operations menu when Ctrl+clicking on nodes  
- Connections: Connection operations menu when Ctrl+clicking on connections

The Vue component handles the UI while this Python wrapper provides
the interface for registering callbacks and managing the menu state.
"""

from nicegui import ui
from typing import Dict, List, Optional, Callable


class ContextMenu(ui.element, component='context_menu.vue'):
    """Vue-based context menu component with event handling."""
    
    def __init__(self, 
                 available_nodes: List[str] = None,
                 on_create_node: Optional[Callable[[str, float, float], None]] = None,
                 on_duplicate_node: Optional[Callable[[str], None]] = None,
                 on_copy_node: Optional[Callable[[str], None]] = None,
                 on_delete_node: Optional[Callable[[str], None]] = None,
                 on_inspect_connection: Optional[Callable[[str], None]] = None,
                 on_delete_connection: Optional[Callable[[str], None]] = None):
        super().__init__()
        
        # Store callbacks
        self._on_create_node = on_create_node
        self._on_duplicate_node = on_duplicate_node
        self._on_copy_node = on_copy_node
        self._on_delete_node = on_delete_node
        self._on_inspect_connection = on_inspect_connection
        self._on_delete_connection = on_delete_connection
        
        # Props for Vue component
        self._props['availableNodes'] = available_nodes or []
        
        # Setup event handlers for Vue component events
        self.on('createNode', self._handle_create_node)
        self.on('duplicateNode', self._handle_duplicate_node)
        self.on('copyNode', self._handle_copy_node)
        self.on('deleteNode', self._handle_delete_node)
        self.on('inspectConnection', self._handle_inspect_connection)
        self.on('deleteConnection', self._handle_delete_connection)
    
    def _handle_create_node(self, event_data):
        """Handle node creation event from Vue component."""
        print(f"[ContextMenu] Create node event: {event_data}")
        if self._on_create_node:
            args = event_data.args
            node_type = args.get('nodeType')
            x = args.get('x', 0)
            y = args.get('y', 0)
            
            if node_type:
                print(f"[ContextMenu] Creating node: {node_type} at ({x}, {y})")
                self._on_create_node(node_type, x, y)
    
    def _handle_duplicate_node(self, event_data):
        """Handle node duplication event from Vue component."""
        print(f"[ContextMenu] Duplicate node event: {event_data}")
        if self._on_duplicate_node:
            args = event_data.args
            node_id = args.get('nodeId')
            if node_id:
                self._on_duplicate_node(node_id)
    
    def _handle_copy_node(self, event_data):
        """Handle node copy event from Vue component."""
        print(f"[ContextMenu] Copy node event: {event_data}")
        if self._on_copy_node:
            args = event_data.args
            node_id = args.get('nodeId')
            if node_id:
                self._on_copy_node(node_id)
    
    def _handle_delete_node(self, event_data):
        """Handle node deletion event from Vue component."""
        print(f"[ContextMenu] Delete node event: {event_data}")
        if self._on_delete_node:
            args = event_data.args
            node_id = args.get('nodeId')
            if node_id:
                self._on_delete_node(node_id)
    
    def _handle_inspect_connection(self, event_data):
        """Handle connection inspection event from Vue component."""
        print(f"[ContextMenu] Inspect connection event: {event_data}")
        if self._on_inspect_connection:
            args = event_data.args
            connection_id = args.get('connectionId')
            if connection_id:
                self._on_inspect_connection(connection_id)
    
    def _handle_delete_connection(self, event_data):
        """Handle connection deletion event from Vue component."""
        print(f"[ContextMenu] Delete connection event: {event_data}")
        if self._on_delete_connection:
            args = event_data.args
            connection_id = args.get('connectionId')
            if connection_id:
                self._on_delete_connection(connection_id)
    
    # Public API Methods
    
    def show_canvas_menu(self, x: float, y: float, canvas_x: float = None, canvas_y: float = None):
        """Show context menu for canvas (node creation)."""
        print(f"[ContextMenu] Showing canvas menu at ({x}, {y})")
        # Use exact coordinates without offset for better precision
        target_data = {
            'x': canvas_x or x,
            'y': canvas_y or y
        }
        self.run_method('showContextMenu', 'canvas', x, y, None, target_data)
    
    def show_node_menu(self, x: float, y: float, node_id: str):
        """Show context menu for node operations."""
        print(f"[ContextMenu] Showing node menu for {node_id} at ({x}, {y})")
        # Use exact coordinates without offset for better precision
        target_data = {'nodeId': node_id}
        self.run_method('showContextMenu', 'node', x, y, None, target_data)
    
    def show_connection_menu(self, x: float, y: float, connection_id: str):
        """Show context menu for connection operations."""
        print(f"[ContextMenu] Showing connection menu for {connection_id} at ({x}, {y})")
        # Use exact coordinates without offset for better precision
        target_data = {'connectionId': connection_id}
        self.run_method('showContextMenu', 'connection', x, y, None, target_data)
    
    def hide_menu(self):
        """Hide the context menu."""
        self.run_method('hideMenu')
    
    def update_available_nodes(self, nodes: List[str]):
        """Update the list of available nodes for creation."""
        self._props['availableNodes'] = nodes
        self.update()
