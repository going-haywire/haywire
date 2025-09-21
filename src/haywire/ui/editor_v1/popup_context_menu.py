"""
PopupContextMenu - NiceGUI-based context menu component using enhanced Popup class

This component provides context menus for different elements in the graph canvas:
- Canvas: Node creation menu when Ctrl+clicking on empty space
- Nodes: Node operations menu when Ctrl+clicking on nodes  
- Connections: Connection operations menu when Ctrl+clicking on connections

Uses the enhanced Popup class that creates elements at page root level to avoid zoom/transform inheritance.
"""

from nicegui import ui, app
from typing import Dict, List, Optional, Callable
from .popup import Popup
from .event_definitions import ConnectionRemovedEvent, NodeCreateRequestEvent, NodeRemoveRequestEvent


class PopupContextMenu:
    """NiceGUI-based context menu using enhanced Popup class with cursor positioning."""
    
    def __init__(self, 
                 available_nodes: List[str] = None,
                 on_emit_event: Optional[Callable[[object], None]] = None):
                
        # New event system
        self._on_emit_event = on_emit_event
        
        self.available_nodes = available_nodes or []
        self._current_popup: Optional[Popup] = None
        self._menu_data: dict = {}
    
    def _close_current_menu(self):
        """Close any currently open menu."""
        if self._current_popup:
            self._current_popup.close()
            self._current_popup.delete()
            self._current_popup = None
    
    def _get_node_display_name(self, node_type: str) -> str:
        """Convert node type to display name."""
        parts = node_type.split(':')
        if len(parts) > 1:
            return parts[-1].replace('.', ' ').title()
        return node_type
    
    # Canvas Actions  
    def _create_node(self, node_type: str):
        """Handle node creation."""
        canvas_x = self._menu_data.get('canvas_x', 0)
        canvas_y = self._menu_data.get('canvas_y', 0)
                
        event = NodeCreateRequestEvent(
            nodeType=node_type,
            position={'x': canvas_x, 'y': canvas_y}
        )
        self._on_emit_event(event)
        self._close_current_menu()

    def _delete_node(self, node_id: str):
        """Handle node deletion."""
        event = NodeRemoveRequestEvent(
            nodeId=node_id
        )
        self._on_emit_event(event)
        self._close_current_menu()

    def _delete_connection(self, connection_id: str):
        """Handle connection deletion."""
        event = ConnectionRemovedEvent(
            connectionId=connection_id
        )
        self._on_emit_event(event)
        self._close_current_menu()

    # Node Actions
    def _duplicate_node(self, node_id: str):
        """Handle node duplication."""
        print(f"[PopupContextMenu] Not Yet implemented: Duplicating node {node_id}")
        # not yet implemented
        self._close_current_menu()
    
    def _copy_node(self, node_id: str):
        """Handle node copying."""
        print(f"[PopupContextMenu] Not Yet implemented: Copying node {node_id}")
        # not yet impleemented
        self._close_current_menu()
        
    # Connection Actions
    def _inspect_connection(self, connection_id: str):
        """Handle connection inspection."""
        print(f"[PopupContextMenu] Not Yet implemented: Inspecting connection {connection_id}")
        # not yet implemented
        self._close_current_menu()
    

    ##############################################
    # Drawing Context Menus at Cursor Position 
    ##############################################

    def show_canvas_menu(self, x: float, y: float, canvas_x: float = None, canvas_y: float = None):
        """Show context menu for canvas (node creation)."""
        self._close_current_menu()
        
        # Store canvas coordinates for node creation
        self._menu_data = {
            'canvas_x': canvas_x if canvas_x is not None else x,
            'canvas_y': canvas_y if canvas_y is not None else y
        }
                
        # Create context menu popup positioned at cursor
        popup = Popup.create_context_menu("Canvas Menu", x + 5, y + 5)
        
        with popup:
            # Node creation section
            ui.label('Create Node').classes('text-xs font-semibold text-gray-600 uppercase mb-2')
            
            with ui.column().classes('w-full gap-1'):
                for node_type in self.available_nodes:
                    display_name = self._get_node_display_name(node_type)
                    btn = ui.button(f'+ {display_name}', on_click=lambda nt=node_type: self._create_node(nt))
                    btn.props('flat align=left')
                    btn.classes('w-full justify-start px-3 py-2 text-gray-700 hover:bg-blue-50 hover:text-blue-600 text-sm')
        
        popup.open()
        self._current_popup = popup
    
    def show_node_menu(self, x: float, y: float, node_id: str):
        """Show context menu for node operations."""
        self._close_current_menu()
        
        # Store node ID for operations
        self._menu_data = {'node_id': node_id}
                
        # Create context menu popup positioned at cursor
        popup = Popup.create_context_menu("Node Menu", x + 5, y + 5)
        
        with popup:
            with ui.column().classes('w-full gap-1'):
                btn1 = ui.button('📋 Duplicate Node', on_click=lambda: self._duplicate_node(node_id))
                btn1.props('flat align=left')
                btn1.classes('w-full justify-start px-3 py-2 text-gray-700 hover:bg-blue-50 hover:text-blue-600 text-sm')
                
                btn2 = ui.button('📄 Copy Node', on_click=lambda: self._copy_node(node_id))
                btn2.props('flat align=left')
                btn2.classes('w-full justify-start px-3 py-2 text-gray-700 hover:bg-blue-50 hover:text-blue-600 text-sm')
                
                btn3 = ui.button('🗑️ Delete Node', on_click=lambda: self._delete_node(node_id))
                btn3.props('flat align=left')
                btn3.classes('w-full justify-start px-3 py-2 text-red-600 hover:bg-red-50 hover:text-red-700 text-sm')
        
        popup.open()
        self._current_popup = popup
    
    def show_connection_menu(self, x: float, y: float, connection_id: str):
        """Show context menu for connection operations."""
        self._close_current_menu()
        
        # Store connection ID for operations  
        self._menu_data = {'connection_id': connection_id}
                
        # Create context menu popup positioned at cursor
        popup = Popup.create_context_menu("Connection Menu", x + 5, y + 5)
        
        with popup:
            with ui.column().classes('w-full gap-1'):
                btn1 = ui.button('🔍 Inspect Connection', on_click=lambda: self._inspect_connection(connection_id))
                btn1.props('flat align=left')
                btn1.classes('w-full justify-start px-3 py-2 text-gray-700 hover:bg-blue-50 hover:text-blue-600 text-sm')
                
                btn2 = ui.button('🗑️ Delete Connection', on_click=lambda: self._delete_connection(connection_id))
                btn2.props('flat align=left')
                btn2.classes('w-full justify-start px-3 py-2 text-red-600 hover:bg-red-50 hover:text-red-700 text-sm')
        
        popup.open()
        self._current_popup = popup
