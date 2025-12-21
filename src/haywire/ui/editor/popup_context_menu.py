"""
PopupContextMenu - NiceGUI-based context menu component using enhanced Popup class

This component provides context menus for different elements in the graph canvas:
- Canvas: Node creation menu when Ctrl+clicking on empty space
- Nodes: Node operations menu when Ctrl+clicking on nodes  
- Connections: Connection operations menu when Ctrl+clicking on connections

Uses the enhanced Popup class that creates elements at page root level 
to avoid zoom/transform inheritance.
"""

from nicegui import ui
from typing import List, Optional, Callable

from haywire.core.node.factory import NodeFactory

from .popup import Popup
from .event_definitions import (
    NodeCreateRequestEvent,
    UserRemoveEvent,
    UserCopySelectedEvent,
    UserPasteClipboardEvent
)
from .node_menu_builder import NodeMenuBuilder


class PopupContextMenu:
    """NiceGUI-based context menu using enhanced Popup class with cursor positioning."""
    
    def __init__(self, 
                 node_factory: NodeFactory,
                 on_emit_event: Optional[Callable[[object], None]] = None,
                 clipboard_checker: Optional[Callable[[], bool]] = None):
                
        self.node_factory = node_factory
        # New event system
        self._on_emit_event = on_emit_event
        self._clipboard_checker = clipboard_checker
        
        self._current_popup: Optional[Popup] = None
        self._menu_data: dict = {}
        
        # Node menu builder for creating hierarchical menus
        self._menu_builder = NodeMenuBuilder(node_factory)
        self._recent_nodes: List[str] = []  # Track recently created nodes
        
        # Setup hot reload listener
        self._setup_hot_reload_listener()
    
    def _close_current_menu(self):
        """Close any currently open menu."""
        if self._current_popup:
            self._current_popup.close()
            self._current_popup.delete()
            self._current_popup = None
    
    def _setup_hot_reload_listener(self):
        """Setup listener for node hot reload events."""
        self.node_factory.add_batch_listener(
            lambda event: self._menu_builder.invalidate_cache()
        )
    
    # Canvas Actions  
    def _create_node(self, registry_key: str):
        """Handle node creation."""
        canvas_x = self._menu_data.get('canvas_x', 0)
        canvas_y = self._menu_data.get('canvas_y', 0)
        
        # Track recently created nodes
        if registry_key not in self._recent_nodes:
            self._recent_nodes.insert(0, registry_key)
            # Keep only last 5 recent nodes
            self._recent_nodes = self._recent_nodes[:5]
                
        event = NodeCreateRequestEvent(
            registryKey=registry_key,
            position={'x': canvas_x, 'y': canvas_y}
        )
        self._on_emit_event(event)
        self._close_current_menu()
    
    def _paste_clipboard(self):
        """Handle paste operation at canvas position."""
        canvas_x = self._menu_data.get('canvas_x', 0)
        canvas_y = self._menu_data.get('canvas_y', 0)
        
        event = UserPasteClipboardEvent(
            canvasX=canvas_x,
            canvasY=canvas_y
        )
        self._on_emit_event(event)
        self._close_current_menu()
    
    def _has_clipboard_content(self) -> bool:
        """Check if clipboard has content available for pasting."""
        if self._clipboard_checker:
            return self._clipboard_checker()
        return False

    def _delete_node(self, node_id: str):
        """Handle node deletion."""
        event = UserRemoveEvent(
            nodes = [node_id,],
            connections=[]
            )
        self._on_emit_event(event)
        self._close_current_menu()

    def _delete_connection(self, connection_id: str):
        """Handle connection deletion."""
        event = UserRemoveEvent(
            nodes = [],
            connections = [connection_id,]
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
        """Handle single node copying."""
        event = UserCopySelectedEvent(
            selectedNodes=[node_id],
            selectedConnections=[]
        )
        self._on_emit_event(event)
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
        """Show enhanced context menu for canvas (node creation) using NodeMenuBuilder."""
        self._close_current_menu()
        
        # Store canvas coordinates for node creation
        self._menu_data = {
            'canvas_x': canvas_x if canvas_x is not None else x,
            'canvas_y': canvas_y if canvas_y is not None else y
        }
                
        # Create context menu popup positioned at cursor
        popup = Popup.create_context_menu("Create Node", x + 5, y + 5)
        
        with popup:
            with ui.column().classes('w-full gap-1'):
                # Add paste option if clipboard has content
                if self._has_clipboard_content():
                    btn_paste = ui.button('📄 Paste', on_click=lambda: self._paste_clipboard())
                    btn_paste.props('flat align=left')
                    btn_paste.classes(
                        'w-full justify-start px-3 py-2 '
                        'text-gray-700 hover:bg-blue-50 hover:text-blue-600 text-sm'
                    )
                    
                    # Add separator if we have paste option
                    ui.separator().classes('w-full my-1')
                
                # Create the hierarchical node menu using NodeMenuBuilder
                self._menu_builder.create_node_menu(
                    on_node_selected=self._handle_node_selection,
                    recent_nodes=self._recent_nodes,
                    show_search=True
                )
        
        popup.open()
        self._current_popup = popup
    
    def _handle_node_selection(self, registry_key: str):
        """Handle when a node is selected from the menu."""
        self._create_node(registry_key)
    


    def show_node_menu(self, x: float, y: float, node_id: str):
        """Show context menu for node operations."""
        self._close_current_menu()
        
        # Store node ID for operations
        self._menu_data = {'node_id': node_id}
                
        # Create context menu popup positioned at cursor
        popup = Popup.create_context_menu("Node Menu", x + 5, y + 5)
        
        with popup:
            with ui.column().classes('w-full gap-1'):
                btn1 = ui.button(
                    '📋 Duplicate Node',
                    on_click=lambda: self._duplicate_node(node_id)
                )
                btn1.props('flat align=left')
                btn1.classes(
                    'w-full justify-start px-3 py-2 '
                    'text-gray-700 hover:bg-blue-50 hover:text-blue-600 text-sm'
                )
                
                btn2 = ui.button('📄 Copy Node', on_click=lambda: self._copy_node(node_id))
                btn2.props('flat align=left')
                btn2.classes(
                    'w-full justify-start px-3 py-2 '
                    'text-gray-700 hover:bg-blue-50 hover:text-blue-600 text-sm'
                )
                
                btn3 = ui.button('🗑️ Delete Node', on_click=lambda: self._delete_node(node_id))
                btn3.props('flat align=left')
                btn3.classes(
                    'w-full justify-start px-3 py-2 '
                    'text-red-600 hover:bg-red-50 hover:text-red-700 text-sm'
                )
        
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
                btn1 = ui.button(
                    '🔍 Inspect Connection',
                    on_click=lambda: self._inspect_connection(connection_id)
                )
                btn1.props('flat align=left')
                btn1.classes(
                    'w-full justify-start px-3 py-2 '
                    'text-gray-700 hover:bg-blue-50 hover:text-blue-600 text-sm'
                )
                
                btn2 = ui.button(
                    '🗑️ Delete Connection',
                    on_click=lambda: self._delete_connection(connection_id)
                )
                btn2.props('flat align=left')
                btn2.classes(
                    'w-full justify-start px-3 py-2 '
                    'text-red-600 hover:bg-red-50 hover:text-red-700 text-sm'
                )
        
        popup.open()
        self._current_popup = popup
    
    def show_selected_menu(
        self,
        x: float,
        y: float,
        selected_nodes: List[str],
        selected_connections: List[str]
    ):
        """Show context menu for multi-selection operations."""
        self._close_current_menu()
        
        # Store selection data for operations  
        self._menu_data = {
            'selected_nodes': selected_nodes,
            'selected_connections': selected_connections
        }
        
        # Create a meaningful title based on selection
        node_count = len(selected_nodes)
        connection_count = len(selected_connections)
        
        if node_count > 0 and connection_count > 0:
            title = f"Selection ({node_count} nodes, {connection_count} connections)"
        elif node_count > 0:
            title = f"Selection ({node_count} {'node' if node_count == 1 else 'nodes'})"
        elif connection_count > 0:
            title = (
                f"Selection ({connection_count} "
                f"{'connection' if connection_count == 1 else 'connections'})"
            )
        else:
            title = "Selection"
                
        # Create context menu popup positioned at cursor
        popup = Popup.create_context_menu(title, x + 5, y + 5)
        
        with popup:
            with ui.column().classes('w-full gap-1'):
                # Delete all selected items
                if node_count > 0 or connection_count > 0:
                    btn1 = ui.button('🗑️ Delete Selected', on_click=lambda: self._delete_selected())
                    btn1.props('flat align=left')
                    btn1.classes(
                        'w-full justify-start px-3 py-2 '
                        'text-red-600 hover:bg-red-50 hover:text-red-700 text-sm'
                    )
                
                # Group selected (placeholder - not implemented yet)
                if node_count > 1:
                    btn2 = ui.button(
                        '📦 Group Nodes',
                        on_click=lambda: self._group_selected_nodes()
                    )
                    btn2.props('flat align=left')
                    btn2.classes(
                        'w-full justify-start px-3 py-2 '
                        'text-gray-700 hover:bg-blue-50 hover:text-blue-600 text-sm'
                    )
                
                # Copy selected (placeholder - not implemented yet)
                if node_count > 0:
                    btn3 = ui.button(
                        '📋 Copy Selected',
                        on_click=lambda: self._copy_selected_nodes()
                    )
                    btn3.props('flat align=left')
                    btn3.classes(
                        'w-full justify-start px-3 py-2 '
                        'text-gray-700 hover:bg-blue-50 hover:text-blue-600 text-sm'
                    )
        
        popup.open()
        self._current_popup = popup
    
    def _delete_selected(self):
        """Handle deletion of all selected items."""
        selected_nodes = self._menu_data.get('selected_nodes', [])
        selected_connections = self._menu_data.get('selected_connections', [])

        event = UserRemoveEvent(
            nodes = selected_nodes,
            connections = selected_connections
        )
        self._on_emit_event(event)
        
        self._close_current_menu()
    
    def _group_selected_nodes(self):
        """Handle grouping of selected nodes (placeholder)."""
        selected_nodes = self._menu_data.get('selected_nodes', [])
        print(f"[PopupContextMenu] Not Yet implemented: Grouping {len(selected_nodes)} nodes")
        # TODO: Implement node grouping
        self._close_current_menu()
    
    def _copy_selected_nodes(self):
        """Handle copying of selected nodes and connections."""
        selected_nodes = self._menu_data.get('selected_nodes', [])
        selected_connections = self._menu_data.get('selected_connections', [])
        
        event = UserCopySelectedEvent(
            selectedNodes=selected_nodes,
            selectedConnections=selected_connections
        )
        self._on_emit_event(event)
        self._close_current_menu()
