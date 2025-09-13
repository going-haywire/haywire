"""
Enhanced DI-based test application with GraphCanvasManager

This application demonstrates:
1. Dedicated GraphCanvasManager for UI management
2. Clean separation between graph logic and UI rendering  
3. JavaScript-based smooth interactions for connections and node movement
4. Integration with undo/redo system
5. Registry-based node system
6. Proper edge management with visual feedback

Key improvements:
- GraphCanvasManager handles all UI interactions
- JavaScript manages real-time visual feedback
- Python manages data model and state changes
- Clean event-driven architecture
"""

import os
import sys
from pathlib import Path
from nicegui import ui, events
import time
import random
import json
from typing import Dict, List, Optional, Tuple

# Add project paths
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__)))
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Haywire imports
from haywire.ui.pan_zoom.zoom_pan_vue import ZoomPanContainer
from haywire.ui.graph_canvas_manager import GraphCanvasManager, register_canvas_manager, unregister_canvas_manager
from haywire.core.graph.graph import HaywireGraph, Edge, EdgeType
from haywire.core.node.node import BaseNode
from haywire.core.node.node_factory import NodeFactory
from haywire.undo.history_manager import HistoryManager
from haywire.undo.interfaces import IHistoryManager
from haywire.undo.config import UndoConfig, DEVELOPMENT_CONFIG
from haywire.undo.actions.graph_actions import (
    AddNodeAction, RemoveNodeAction, MoveNodeAction, 
    AddEdgeAction, RemoveEdgeAction, ChangeSelectionAction, SelectionState
)

# DI imports  
from haywire.core.di.config import create_library_system_service

# Import UI components for proper node rendering
from haywire.ui.ui_node import UINode


class UndoRedoTestAppWithCanvasManager:
    """Enhanced test application with dedicated GraphCanvasManager."""
    
    def __init__(self):
        print("Setting up Enhanced DI system with Canvas Manager...")
        
        # Initialize library system service (shared across all sessions)
        self.setup_library_system()
        
        # Shared data across all sessions
        self.setup_shared_services()
        
        # Session-specific UI state (client_id -> session_data)
        self.sessions = {}
        
    def get_session_data(self):
        """Get or create session-specific data for current client."""
        from nicegui import context
        
        # Use NiceGUI's client context to identify unique sessions
        client_id = context.client.id if context.client else 'default'
        
        if client_id not in self.sessions:
            print(f"Creating new session for client: {client_id}")
            self.sessions[client_id] = self.create_session_data()
        
        return self.sessions[client_id], client_id
    
    def create_session_data(self):
        """Create session-specific UI data (not graph data - that's shared)."""
        return {
            # UI-specific state (not shared between sessions)
            # Note: selection is now managed by the shared graph, not per-session
            'creation_mode': None,
            'canvas_manager': None,
            'zoom_container': None,
            'stats': {
                'nodes_created': 0,
                'edges_created': 0,
                'undo_operations': 0,
                'redo_operations': 0
            },
            'ui_containers': {}  # Store UI container references
        }
    
    def setup_shared_services(self):
        """Setup services and data shared across all sessions."""
        # Get services from the library system (shared)
        self.node_registry = self.library_service.get_node_registry()
        self.node_factory = self.library_service.get_node_factory()
        self.node_render_factory = self.library_service.get_node_render_factory()
        self.history_manager = self.library_service.get_history_manager()
        
        # Create ONE shared graph for all sessions
        self.graph = HaywireGraph("shared_graph", "Shared Graph Across Sessions")
        
        # Global stats (shared across sessions)
        self.global_stats = {
            'nodes_created': 0,
            'edges_created': 0,
            'undo_operations': 0,
            'redo_operations': 0
        }
        
        print(f"History manager available: {self.history_manager is not None}")
        print("Shared services configured successfully.")
    
    def setup_library_system(self):
        """Initialize the library system service."""
        # Store undo config for UI access
        self.undo_config = DEVELOPMENT_CONFIG
        
        # Create and initialize the library system service with undo support
        self.library_service = create_library_system_service(
            project_root=project_root,
            enable_file_watching=True,
            undo_config=self.undo_config
        )
        
        print("Enhanced DI system initialized successfully.")
        
        # Print registry status to see what nodes are available
        self.library_service.print_registry_status()
    
    def setup_services(self):
        """Get all required services from the library system."""
        # Services will now be accessed per session
        # Remove the old global service setup
        pass
    
    def get_available_nodes(self):
        """Get available node types from the registry."""
        # Use shared node registry
        available_nodes = self.node_registry.list_names()
        print(f"Available nodes from registry: {available_nodes}")
        return available_nodes
    
    def create_ui(self):
        """Create the main UI."""
        @ui.page('/', title="Enhanced Haywire Test App with Canvas Manager")
        def main_page():
            # Get session-specific data
            session_data, client_id = self.get_session_data()
            
            # Store current session in UI context
            self.current_session = session_data
            self.current_client_id = client_id
            
            print(f"Creating UI for session: {client_id[:8]}")
            
            self.create_header()
            
            with ui.row().classes('w-full flex-grow gap-4 p-4').style('height: calc(100vh - 80px);'):
                self.create_left_panel()
                self.create_main_editor()
                self.create_right_panel()
    
    def create_header(self):
        """Create the application header with main controls."""
        with ui.header().classes('bg-blue-600 text-white px-4 py-2'):
            with ui.row().classes('w-full justify-between items-center'):
                with ui.row().classes('items-center gap-4'):
                    ui.label(f'Enhanced Haywire Test App - Session {self.current_client_id[:8]}').classes('text-xl font-bold')
                    
                    # Quick action buttons
                    ui.button('Undo', icon='undo', on_click=self.undo_action).props('outline').classes('text-white')
                    ui.button('Redo', icon='redo', on_click=self.redo_action).props('outline').classes('text-white')
                    ui.button('Clear All', icon='clear_all', on_click=self.clear_graph).props('outline').classes('text-white')
    
    def create_left_panel(self):
        """Create the left control panel."""
        with ui.card().classes('w-80 overflow-auto').style('height: calc(100vh - 120px);'):
            ui.label('Controls & Tools').classes('text-lg font-bold mb-4')
            
            # Canvas Manager Status
            with ui.expansion('Canvas Manager Status', icon='dashboard').classes('w-full'):
                with ui.column() as canvas_status_container:
                    # Store reference in session data
                    self.current_session['ui_containers']['canvas_status_container'] = canvas_status_container
                    ui.label('Canvas Manager: Initializing...').classes('text-sm text-gray-600')
            
            # Connection Help
            with ui.expansion('Connection Instructions', icon='help').classes('w-full'):
                with ui.column().classes('gap-2'):
                    ui.label('How to create connections:').classes('font-bold text-sm')
                    ui.label('1. Create some nodes first').classes('text-xs')
                    ui.label('2. Look for colored circles (pins) on nodes').classes('text-xs')
                    ui.label('3. Click and drag from one pin to another').classes('text-xs')
                    ui.label('4. Blue pins = outputs, Red pins = inputs').classes('text-xs')
                    ui.label('5. You can only connect output → input').classes('text-xs')
                    ui.label('6. Click on a connection line to delete it').classes('text-xs')
            
            # Node creation tools
            with ui.expansion('Node Creation', icon='add_circle').classes('w-full'):
                ui.label('Click a node type, then click on canvas to create:').classes('text-sm mb-2')
                
                available_nodes = self.get_available_nodes()
                if available_nodes:
                    for node_type in available_nodes:
                        # Capture session data for this button's callback
                        session_data = self.current_session
                        ui.button(
                            f'Create {node_type}', 
                            on_click=lambda node_type=node_type, sess=session_data: self.set_creation_mode_for_session(sess, node_type),
                            icon='add'
                        ).props('outline').classes('w-full mb-1')
                else:
                    ui.label('No nodes available from registry').classes('text-orange-600')
            
            # Tools
            with ui.expansion('Tools', icon='build').classes('w-full'):
                with ui.column().classes('gap-2'):
                    ui.button('Selection Mode', on_click=self.toggle_selection_mode, icon='mouse').props('outline')
                    ui.button('Delete Selected', on_click=self.delete_selected, icon='delete').props('outline color=negative')
                    ui.button('Random Graph', on_click=self.create_random_graph, icon='shuffle').props('outline')
            
            # Debug Tools
            with ui.expansion('Debug Tools', icon='bug_report').classes('w-full'):
                with ui.column().classes('gap-2'):
                    ui.button('Debug Pins', on_click=self.debug_pins, icon='radio_button_checked').props('outline color=primary')
                    ui.button('Debug Connections', on_click=self.debug_connections, icon='cable').props('outline color=primary')
                    ui.button('Test Simple Pin', on_click=self.test_simple_pin, icon='circle').props('outline color=accent')
            
            # Statistics
            with ui.expansion('Statistics', icon='analytics').classes('w-full'):
                with ui.column() as stats_container:
                    self.current_session['ui_containers']['stats_container'] = stats_container
                    self.update_stats_display()
            
            # Configuration
            with ui.expansion('Undo/Redo Config', icon='settings').classes('w-full'):
                with ui.column().classes('gap-2'):
                    if self.history_manager:
                        ui.switch(
                            'Auto Group Actions', 
                            value=self.undo_config.enable_auto_grouping,
                            on_change=lambda e: self.toggle_auto_grouping(e.value)
                        )
                        ui.switch(
                            'Merge Similar Actions',
                            value=self.undo_config.enable_action_merging, 
                            on_change=lambda e: self.toggle_action_merging(e.value)
                        )
                        ui.number(
                            'Max Undo Actions',
                            value=self.undo_config.max_actions,
                            min=1, max=1000,
                            on_change=lambda e: self.set_max_actions(int(e.value))
                        )
                    else:
                        ui.label('Undo system not available').classes('text-gray-500')
    
    def create_main_editor(self):
        """Create the main node editor with GraphCanvasManager."""
        with ui.card().classes('flex-grow').style('min-width: 600px; height: calc(100vh - 120px);'):
            ui.label(f'Node Editor - Session {self.current_client_id[:8]}').classes('text-lg font-bold mb-2')
            
            # Capture current session data for callbacks
            session_data = self.current_session
            client_id = self.current_client_id
            
            # Create session-specific zoom container with captured session
            zoom_container = ZoomPanContainer(
                min_zoom=0.1,
                max_zoom=3.0,
                initial_zoom=1.0,
                on_zoom_change=lambda zoom: self.on_zoom_change_for_specific_session(session_data, zoom),
                on_pan_change=lambda x, y: self.on_pan_change_for_specific_session(session_data, x, y)
            ).classes('w-full flex-grow border-2 border-gray-300').style('height: calc(100% - 60px);')
            
            session_data['zoom_container'] = zoom_container
            
            # Create session-specific canvas manager with captured session
            canvas_manager = GraphCanvasManager(
                graph=self.graph,  # Use shared graph
                node_render_factory=self.node_render_factory,  # Use shared render factory
                zoom_container=zoom_container,
                on_node_position_changed=lambda node_id, pos: self.on_node_moved_for_specific_session(session_data, node_id, pos),
                on_connection_created=lambda s_id, s_port, e_id, e_port: self.on_connection_created_for_specific_session(session_data, s_id, s_port, e_id, e_port),
                on_connection_removed=lambda edge: self.on_connection_removed_for_specific_session(session_data, edge),
                on_node_selected=lambda node_id, selected: self.on_node_selected_for_specific_session(session_data, node_id, selected),
                history_manager=self.history_manager  # Pass the shared history manager
            )
            
            session_data['canvas_manager'] = canvas_manager
            
            # Register canvas manager with unique session ID
            register_canvas_manager(canvas_manager)
            
            # Setup client-side interactions
            canvas_manager.setup_client_side_interactions()
            
            # IMPORTANT: Sync with existing graph data when canvas manager is first created
            canvas_manager.sync_with_graph()
            print(f"Canvas manager synced with {len(self.graph.nodes)} existing nodes")
            
            # Add canvas click handler for node creation with captured session
            canvas_manager.canvas.on('click', lambda event: self.on_canvas_click_for_specific_session(session_data, client_id, event))
            
            self.create_zoom_controls()
            
            # Update canvas status
            self.update_canvas_status()
    
    def create_right_panel(self):
        """Create the right information panel."""
        with ui.card().classes('w-80 overflow-auto').style('height: calc(100vh - 120px);'):
            ui.label('Information & History').classes('text-lg font-bold mb-4')
            
            # Graph Information
            with ui.expansion('Graph Info', icon='info').classes('w-full'):
                with ui.column() as info_container:
                    self.current_session['ui_containers']['info_container'] = info_container
                    self.update_info_display()
            
            # History Information
            with ui.expansion('Undo/Redo History', icon='history').classes('w-full'):
                with ui.column() as history_container:
                    self.current_session['ui_containers']['history_container'] = history_container
                    self.update_history_display()
            
            # Selected Nodes
            with ui.expansion('Selection', icon='check_circle').classes('w-full'):
                with ui.column() as selection_container:
                    self.current_session['ui_containers']['selection_container'] = selection_container
                    ui.label('No nodes selected').classes('text-gray-500')
    
    def create_zoom_controls(self):
        """Create zoom and pan controls."""
        with ui.row().classes('gap-2 mt-2'):
            ui.button('Fit to View', on_click=lambda: self.current_session['zoom_container'].zoom_to_fit(), icon='fit_screen').props('outline')
            ui.button('Reset Zoom', on_click=lambda: self.current_session['zoom_container'].reset_zoom(), icon='center_focus_strong').props('outline')
            ui.button('Zoom In', on_click=lambda: self.current_session['zoom_container'].zoom_in(), icon='zoom_in').props('outline')
            ui.button('Zoom Out', on_click=lambda: self.current_session['zoom_container'].zoom_out(), icon='zoom_out').props('outline')
    
    # Session-specific Event Handlers
    def on_zoom_change_for_session(self, zoom_level):
        """Handle zoom change events for specific session."""
        self.update_canvas_status()
    
    def on_pan_change_for_session(self, pan_x, pan_y):
        """Handle pan change events for specific session.""" 
        self.update_canvas_status()
    
    # Session-specific Event Handlers with captured session data
    def on_zoom_change_for_specific_session(self, session_data, zoom_level):
        """Handle zoom change events for specific session."""
        self.update_displays_for_session(session_data)
    
    def on_pan_change_for_specific_session(self, session_data, pan_x, pan_y):
        """Handle pan change events for specific session.""" 
        self.update_displays_for_session(session_data)
    
    def on_canvas_click_for_specific_session(self, session_data, client_id, event):
        """Handle canvas click events for specific session."""
        if session_data['creation_mode']:
            try:
                # Get click position from event
                click_x = event.args.get('offsetX', 100)
                click_y = event.args.get('offsetY', 100)
                
                # Store creation details for async execution
                node_type = session_data['creation_mode']
                session_data['creation_mode'] = None  # Reset immediately
                
                # Use timer to execute in proper UI context
                ui.timer(0.01, lambda: self._create_node_in_specific_session(session_data, client_id, node_type, click_x, click_y), once=True)
                
            except Exception as e:
                ui.notify(f"Error creating node: {str(e)}", type='negative')
                print(f"Error creating node: {e}")
    
    def _create_node_in_specific_session(self, session_data, client_id, node_type: str, click_x: float, click_y: float):
        """Create node within specific session context."""
        try:
            # Create node using shared factory and graph
            node = self.node_factory.create_instance(
                node_type,
                self.graph,  # Use shared graph
                position=(click_x, click_y)
            )
            
            # Set position attributes
            node.ui_posX = click_x
            node.ui_posY = click_y
            
            # Use shared undo system
            if self.history_manager:
                action = AddNodeAction(self.graph, node)
                self.history_manager.add_action(action)
            else:
                self.graph.add_node(node)
            
            # Add visual representation through this session's canvas manager
            if session_data['canvas_manager'].add_node_visual(node, (click_x, click_y)):
                # Update global stats
                self.global_stats['nodes_created'] += 1
                # Sync all sessions to show the new node
                self.sync_all_sessions()
                # Update UI displays for this specific session
                self.update_displays_for_session(session_data)
                ui.notify(f"Created {node.__class__.__name__} at ({click_x}, {click_y})")
            else:
                ui.notify(f"Failed to create visual for {node.__class__.__name__}", type='negative')
                
        except Exception as e:
            ui.notify(f"Error creating node: {str(e)}", type='negative')
            print(f"Error creating node: {e}")
    
    def on_node_moved_for_specific_session(self, session_data, node_id: str, new_position: Tuple[float, float]):
        """Handle node position changes for specific session."""
        try:
            if node_id in self.graph.nodes:
                node = self.graph.nodes[node_id]
                old_position = (getattr(node, 'ui_posX', 0), getattr(node, 'ui_posY', 0))
                
                # Only create an action if the position has actually changed
                if old_position != new_position:
                    print(f"DEBUG: Node move - {node_id}: {old_position} -> {new_position}")
                    
                    if self.history_manager:
                        # Pass individual coordinates, not tuples
                        action = MoveNodeAction(self.graph, node_id, new_position[0], new_position[1])
                        self.history_manager.add_action(action)
                        # NOTE: The action already updates the position, so no need to do it manually
                        
                        # Sync all sessions to show the move across all clients
                        self.sync_all_sessions()
                    else:
                        # Fallback if no history manager
                        node.ui_posX, node.ui_posY = new_position
                        # Still need to sync for fallback case
                        self.sync_all_sessions()
                else:
                    print(f"DEBUG: Node move ignored - {node_id}: position unchanged {old_position}")
                
        except Exception as e:
            print(f"Error handling node move: {e}")
    
    def on_connection_created_for_specific_session(self, session_data, start_node_id: str, start_port: str, end_node_id: str, end_port: str):
        """Handle new connection creation for specific session."""
        try:
            print(f"Connection request from session: {start_node_id}:{start_port} -> {end_node_id}:{end_port}")
            
            # Create edge in shared graph
            edge = Edge(
                edge_type=EdgeType.DATA,
                output_node_id=start_node_id,
                outlet_pin_id=start_port,
                input_node_id=end_node_id,
                inlet_pin_id=end_port
            )
            
            # Use shared undo system
            if self.history_manager:
                action = AddEdgeAction(self.graph, edge)
                self.history_manager.add_action(action)
            else:
                self.graph.add_edge(edge)
            
            self.global_stats['edges_created'] += 1
            self.sync_all_sessions()
            # Update UI displays for this specific session
            self.update_displays_for_session(session_data)
            
            ui.notify(f"Connected {start_node_id}:{start_port} → {end_node_id}:{end_port}")
            
        except Exception as e:
            ui.notify(f"Connection failed: {str(e)}", type='negative')
            print(f"Connection error: {e}")
    
    def on_connection_removed_for_specific_session(self, session_data, edge: Edge):
        """Handle connection removal for specific session."""
        try:
            print(f"Connection removal request: {edge.output_node_id} -> {edge.input_node_id}")
            
            # Remove edge from shared graph
            removed = self.graph.remove_edge(
                edge.output_node_id, 
                edge.outlet_pin_id,
                edge.input_node_id, 
                edge.inlet_pin_id
            )
            
            if removed:
                self.sync_all_sessions()
                # Update UI displays for this specific session
                self.update_displays_for_session(session_data)
                ui.notify("Connection removed")
            else:
                ui.notify("Connection not found", type='warning')
            
        except Exception as e:
            print(f"Error removing connection: {e}")
            ui.notify(f"Error removing connection: {str(e)}", type='negative')
    
    def on_node_selected_for_specific_session(self, session_data, node_id: str, selected: bool):
        """Handle node selection changes for specific session."""
        # Selection is now managed by the shared graph through undo actions
        # This callback is deprecated but kept for backward compatibility
        print(f"Node {node_id} {'selected' if selected else 'deselected'} (handled via undo actions)")
        # Update selection display for this specific session
        self.update_selection_display_for_session(session_data)
    
    def on_canvas_click_for_session(self, event):
        """Handle canvas click events for specific session."""
        if self.current_session['creation_mode']:
            try:
                # Get click position from event
                click_x = event.args.get('offsetX', 100)
                click_y = event.args.get('offsetY', 100)
                
                # Store creation details for async execution
                node_type = self.current_session['creation_mode']
                self.current_session['creation_mode'] = None  # Reset immediately
                
                # Use timer to execute in proper UI context
                ui.timer(0.01, lambda: self._create_node_in_ui_context(node_type, click_x, click_y), once=True)
                
            except Exception as e:
                ui.notify(f"Error creating node: {str(e)}", type='negative')
                print(f"Error creating node: {e}")
    
    def on_canvas_click(self, event):
        """Handle canvas click events."""
        if self.creation_mode:
            try:
                # Get click position from event
                click_x = event.args.get('offsetX', 100)
                click_y = event.args.get('offsetY', 100)
                
                # Store creation details for async execution
                node_type = self.creation_mode
                self.creation_mode = None  # Reset immediately
                
                # Use timer to execute in proper UI context
                ui.timer(0.01, lambda: self._create_node_in_ui_context(node_type, click_x, click_y), once=True)
                
            except Exception as e:
                ui.notify(f"Error creating node: {str(e)}", type='negative')
                print(f"Error creating node: {e}")
    
    def _create_node_in_ui_context(self, node_type: str, click_x: float, click_y: float):
        """Create node within proper UI context."""
        try:
            # Create node using shared factory and graph
            node = self.node_factory.create_instance(
                node_type,
                self.graph,  # Use shared graph
                position=(click_x, click_y)
            )
            
            # Set position attributes
            node.ui_posX = click_x
            node.ui_posY = click_y
            
            # Use shared undo system
            if self.history_manager:
                action = AddNodeAction(self.graph, node)
                self.history_manager.add_action(action)
            else:
                self.graph.add_node(node)
            
            # Add visual representation through current session's canvas manager
            if self.current_session['canvas_manager'].add_node_visual(node, (click_x, click_y)):
                # Update global stats
                self.global_stats['nodes_created'] += 1
                # Sync all sessions to show the new node
                self.sync_all_sessions()
                # Update UI displays only for current session
                self.update_current_session_displays()
                ui.notify(f"Created {node.__class__.__name__} at ({click_x}, {click_y})")
            else:
                ui.notify(f"Failed to create visual for {node.__class__.__name__}", type='negative')
                
        except Exception as e:
            ui.notify(f"Error creating node: {str(e)}", type='negative')
            print(f"Error creating node: {e}")
    
    def sync_all_sessions(self):
        """Synchronize all active sessions with the shared graph."""
        sessions_to_remove = []
        
        for client_id, session_data in list(self.sessions.items()):
            if session_data.get('canvas_manager'):
                try:
                    canvas_manager = session_data['canvas_manager']
                    # Ensure each session's canvas manager syncs properly
                    print(f"Syncing session {client_id[:8]} with graph data")
                    canvas_manager.sync_with_graph()
                    
                    # Force update displays for each session
                    self.update_displays_for_session(session_data)
                    
                    print(f"Synced graph data for session {client_id[:8]}")
                except RuntimeError as e:
                    if "client this element belongs to has been deleted" in str(e):
                        print(f"Client {client_id[:8]} disconnected, marking for cleanup")
                        sessions_to_remove.append(client_id)
                    else:
                        print(f"Runtime error syncing session {client_id[:8]}: {e}")
                except Exception as e:
                    print(f"Error syncing session {client_id[:8]}: {e}")
        
        # Clean up disconnected sessions
        for client_id in sessions_to_remove:
            print(f"Removing disconnected session: {client_id[:8]}")
            del self.sessions[client_id]
    
    def update_current_session_displays(self):
        """Update displays only for the current session."""
        if hasattr(self, 'current_session'):
            self.update_displays_for_session(self.current_session)
    
    def update_displays_for_session(self, session_data):
        """Update displays for a specific session."""
        try:
            containers = session_data.get('ui_containers', {})
            
            # Update stats display
            if 'stats_container' in containers:
                container = containers['stats_container']
                container.clear()
                with container:
                    ui.label(f'Nodes Created: {self.global_stats["nodes_created"]}')
                    ui.label(f'Connections Created: {self.global_stats["edges_created"]}')
                    ui.label(f'Undo Operations: {self.global_stats["undo_operations"]}')
                    ui.label(f'Redo Operations: {self.global_stats["redo_operations"]}')
            
            # Update info display
            if 'info_container' in containers:
                container = containers['info_container']
                container.clear()
                with container:
                    ui.label(f'Graph ID: {self.graph.graph_id}').classes('text-sm')
                    ui.label(f'Nodes: {len(self.graph.nodes)}')
                    ui.label(f'Connections: {len(self.graph.edges)}')
                    
                    if self.history_manager:
                        ui.label(f'Can Undo: {self.history_manager.can_undo()}')
                        ui.label(f'Can Redo: {self.history_manager.can_redo()}')
            
            # Update canvas status
            if 'canvas_status_container' in containers and session_data.get('canvas_manager'):
                container = containers['canvas_status_container']
                container.clear()
                with container:
                    ui.label(f'✓ Canvas Manager Active').classes('text-green-600 text-sm')
                    ui.label(f'Visual Nodes: {len(session_data["canvas_manager"].node_panels)}').classes('text-sm')
                    ui.label(f'Visual Connections: {len(session_data["canvas_manager"].connection_paths)}').classes('text-sm')
                    if session_data.get('zoom_container'):
                        zoom_container = session_data['zoom_container']
                        ui.label(f'Zoom: {zoom_container.current_zoom:.2f}x').classes('text-sm')
                        ui.label(f'Pan: ({zoom_container.pan_x:.0f}, {zoom_container.pan_y:.0f})').classes('text-sm')
            
            # Update history display for this specific session
            self.update_history_display_for_session(session_data)
            
            # Update selection display for this specific session
            self.update_selection_display_for_session(session_data)
                        
        except Exception as e:
            print(f"Error updating displays for session: {e}")
    
    # Session-specific event handlers that update shared data
    def on_connection_created_for_session(self, start_node_id: str, start_port: str, end_node_id: str, end_port: str):
        """Handle new connection creation from any session."""
        try:
            print(f"Connection request: {start_node_id}:{start_port} -> {end_node_id}:{end_port}")
            
            # Create edge in shared graph
            edge = Edge(
                edge_type=EdgeType.DATA,
                output_node_id=start_node_id,
                outlet_pin_id=start_port,
                input_node_id=end_node_id,
                inlet_pin_id=end_port
            )
            
            # Use shared undo system
            if self.history_manager:
                action = AddEdgeAction(self.graph, edge)
                self.history_manager.add_action(action)
            else:
                self.graph.add_edge(edge)
            
            self.global_stats['edges_created'] += 1
            self.sync_all_sessions()
            # Update UI displays only for current session
            self.update_current_session_displays()
            
            ui.notify(f"Connected {start_node_id}:{start_port} → {end_node_id}:{end_port}")
            
        except Exception as e:
            ui.notify(f"Connection failed: {str(e)}", type='negative')
            print(f"Connection error: {e}")
    
    def on_connection_removed_for_session(self, edge: Edge):
        """Handle connection removal from any session."""
        try:
            print(f"Connection removal request: {edge.output_node_id} -> {edge.input_node_id}")
            
            # Remove edge from shared graph
            removed = self.graph.remove_edge(
                edge.output_node_id, 
                edge.outlet_pin_id,
                edge.input_node_id, 
                edge.inlet_pin_id
            )
            
            if removed:
                self.sync_all_sessions()
                # Update UI displays only for current session
                self.update_current_session_displays()
                ui.notify("Connection removed")
            else:
                ui.notify("Connection not found", type='warning')
            
        except Exception as e:
            print(f"Error removing connection: {e}")
            ui.notify(f"Error removing connection: {str(e)}", type='negative')
    
    def on_node_moved_for_session(self, node_id: str, new_position: Tuple[float, float]):
        """Handle node position changes from any session."""
        try:
            if node_id in self.graph.nodes:
                node = self.graph.nodes[node_id]
                old_position = (getattr(node, 'ui_posX', 0), getattr(node, 'ui_posY', 0))
                
                if self.history_manager:
                    # Pass individual coordinates, not tuples
                    action = MoveNodeAction(self.graph, node_id, new_position[0], new_position[1])
                    self.history_manager.add_action(action)
                    # NOTE: The action already updates the position, so no need to do it manually
                else:
                    # Fallback if no history manager
                    node.ui_posX, node.ui_posY = new_position
                
        except Exception as e:
            print(f"Error handling node move: {e}")
    
    def on_node_selected_for_session(self, node_id: str, selected: bool):
        """Handle node selection changes (session-specific)."""
        # Selection is now managed by the shared graph through undo actions
        # This callback is deprecated but kept for backward compatibility
        session_data = self.current_session
        print(f"Node {node_id} {'selected' if selected else 'deselected'} (handled via undo actions)")
        # Update selection display for this session only
        self.update_selection_display_for_session(session_data)
    
    def update_selection_display_for_session(self, session_data):
        """Update selection display for specific session."""
        try:
            containers = session_data.get('ui_containers', {})
            if 'selection_container' in containers:
                container = containers['selection_container']
                container.clear()
                with container:
                    # Get selection from shared graph instead of session-local state
                    selected_nodes, selected_connections = self.graph.get_selection_state()
                    total_selected = len(selected_nodes) + len(selected_connections)
                    
                    if total_selected > 0:
                        ui.label(f'Selected: {len(selected_nodes)} nodes, {len(selected_connections)} connections').classes('font-bold')
                        
                        # Show first 5 selected nodes
                        for node_id in list(selected_nodes)[:5]:
                            ui.label(f'• Node: {node_id}').classes('text-xs pl-2')
                        if len(selected_nodes) > 5:
                            ui.label(f'... and {len(selected_nodes) - 5} more nodes').classes('text-xs pl-2 text-gray-500')
                        
                        # Show first 3 selected connections
                        for connection_id in list(selected_connections)[:3]:
                            ui.label(f'• Connection: {connection_id[:30]}...').classes('text-xs pl-2')
                        if len(selected_connections) > 3:
                            ui.label(f'... and {len(selected_connections) - 3} more connections').classes('text-xs pl-2 text-gray-500')
                    else:
                        ui.label('No nodes selected').classes('text-gray-500')
        except Exception as e:
            print(f"Error updating selection display: {e}")
    
    def on_connection_created(self, start_node_id: str, start_port: str, end_node_id: str, end_port: str):
        """Handle new connection creation from canvas manager."""
        try:
            print(f"Connection request: {start_node_id}:{start_port} -> {end_node_id}:{end_port}")
            
            # Create edge in graph
            edge = Edge(
                edge_type=EdgeType.DATA,
                output_node_id=start_node_id,
                outlet_pin_id=start_port,
                input_node_id=end_node_id,
                inlet_pin_id=end_port
            )
            
            # Use undo system
            if self.history_manager:
                action = AddEdgeAction(self.graph, edge)
                self.history_manager.add_action(action)
            else:
                self.graph.add_edge(edge)
            
            # Visual will be handled by canvas manager sync
            self.canvas_manager.sync_with_graph()
            
            self.global_stats['edges_created'] += 1
            self.update_displays()
            
            ui.notify(f"Connected {start_node_id}:{start_port} → {end_node_id}:{end_port}")
            
        except Exception as e:
            ui.notify(f"Connection failed: {str(e)}", type='negative')
            print(f"Connection error: {e}")
    
    def on_connection_removed(self, edge: Edge):
        """Handle connection removal from canvas manager."""
        try:
            print(f"Connection removal request: {edge.output_node_id} -> {edge.input_node_id}")
            
            # Find and remove edge from graph using the correct method
            removed = self.graph.remove_edge(
                edge.output_node_id, 
                edge.outlet_pin_id,
                edge.input_node_id, 
                edge.inlet_pin_id
            )
            
            if removed:
                # For undo system, we'll need to create a proper RemoveEdgeAction
                # but for now, just sync the UI
                self.canvas_manager.sync_with_graph()
                self.update_displays()
                ui.notify("Connection removed")
            else:
                ui.notify("Connection not found", type='warning')
            
        except Exception as e:
            print(f"Error removing connection: {e}")
            ui.notify(f"Error removing connection: {str(e)}", type='negative')
    
    def on_node_moved(self, node_id: str, new_position: Tuple[float, float]):
        """Handle node position changes from canvas manager."""
        try:
            if node_id in self.graph.nodes:
                node = self.graph.nodes[node_id]
                old_position = (getattr(node, 'ui_posX', 0), getattr(node, 'ui_posY', 0))
                
                if self.history_manager:
                    # Pass individual coordinates, not tuples
                    action = MoveNodeAction(self.graph, node_id, new_position[0], new_position[1])
                    self.history_manager.add_action(action)
                    # NOTE: The action already updates the position, so no need to do it manually
                else:
                    # Fallback if no history manager
                    node.ui_posX, node.ui_posY = new_position
                
        except Exception as e:
            print(f"Error handling node move: {e}")
    
    def on_node_selected(self, node_id: str, selected: bool):
        """Handle node selection changes."""
        # Selection is now managed by the shared graph through undo actions
        # This callback is deprecated but kept for backward compatibility
        print(f"Node {node_id} {'selected' if selected else 'deselected'} (handled via undo actions)")
        # Update selection display - will read from shared graph
        self.update_current_session_displays()
    
    def on_hot_reload(self, registry_key: str, affected_node_ids: List[str]):
        """Handle hot reload notifications."""
        print(f"Hot reload detected for {registry_key}, affecting nodes: {affected_node_ids}")
        ui.notify(f"Hot reload: {registry_key} ({len(affected_node_ids)} nodes)", type='info')
    
    # Action Methods
    def set_creation_mode(self, node_type: str):
        """Set node creation mode for current session."""
        if hasattr(self, 'current_session'):
            self.current_session['creation_mode'] = node_type
        else:
            # Fallback for backward compatibility
            self.creation_mode = node_type
        print(f"Setting creation mode to: {node_type}")
        ui.notify(f"Creation mode: {node_type}. Click on canvas to create node.")
    
    def set_creation_mode_for_session(self, session_data, node_type: str):
        """Set node creation mode for a specific session."""
        session_data['creation_mode'] = node_type
        print(f"Setting creation mode to: {node_type} for specific session")
        ui.notify(f"Creation mode: {node_type}. Click on canvas to create node.")
    
    def toggle_selection_mode(self):
        """Toggle selection mode."""
        print("Selection mode toggled")
        ui.notify("Selection mode toggled")
    
    def delete_selected(self):
        """Delete selected nodes."""
        if self.selected_nodes:
            selected_list = list(self.selected_nodes)
            for node_id in selected_list:
                if node_id in self.graph.nodes:
                    node = self.graph.nodes[node_id]
                    
                    if self.history_manager:
                        action = RemoveNodeAction(self.graph, node_id, node)
                        self.history_manager.add_action(action)
                    else:
                        self.graph.remove_node(node_id)
            
            self.canvas_manager.sync_with_graph()
            self.selected_nodes.clear()
            self.update_displays()
            ui.notify(f"Deleted {len(selected_list)} nodes")
        else:
            ui.notify("No nodes selected")
    
    def undo_action(self):
        """Perform undo operation."""
        if self.history_manager and self.history_manager.can_undo():
            nodes_before = set(self.graph.nodes.keys())
            self.history_manager.undo()
            nodes_after = set(self.graph.nodes.keys())
            
            self.global_stats['undo_operations'] += 1
            self.sync_ui_with_graph(nodes_before, nodes_after)
            ui.notify("Undo performed")
        else:
            ui.notify("Nothing to undo")
    
    def redo_action(self):
        """Perform redo operation."""
        if self.history_manager and self.history_manager.can_redo():
            nodes_before = set(self.graph.nodes.keys())
            self.history_manager.redo()
            nodes_after = set(self.graph.nodes.keys())
            
            self.global_stats['redo_operations'] += 1
            self.sync_ui_with_graph(nodes_before, nodes_after)
            ui.notify("Redo performed")
        else:
            ui.notify("Nothing to redo")
    
    def sync_ui_with_graph(self, nodes_before: set, nodes_after: set):
        """Synchronize UI with graph changes across all sessions."""
        # Store current session context to restore later
        original_current_session = getattr(self, 'current_session', None)
        
        try:
            # Sync all active sessions with the updated graph state
            self.sync_all_sessions()
            self.update_displays()
        finally:
            # Restore original session context
            if original_current_session is not None:
                self.current_session = original_current_session
    
    def clear_graph(self):
        """Clear the entire graph."""
        if self.history_manager:
            # Clear through undo system
            node_ids = list(self.graph.nodes.keys())
            for node_id in node_ids:
                node = self.graph.nodes.get(node_id)
                if node:
                    action = RemoveNodeAction(self.graph, node_id, node)
                    self.history_manager.execute(action)
        else:
            self.graph.nodes.clear()
            self.graph.edges.clear()
        
        # Canvas manager handles visual cleanup
        self.canvas_manager.sync_with_graph()
        self.selected_nodes.clear()
        
        self.update_displays()
        ui.notify("Graph cleared")
    
    # Debug Methods
    def debug_pins(self):
        """Debug function to check pin visibility and interaction"""
        ui.notify('Checking pins in browser console...', type='info')
        
        ui.run_javascript("""
        console.log('=== PIN DEBUG SESSION ===');
        
        // Check all connection pins
        const allPins = document.querySelectorAll('.connection-pin');
        console.log(`Found ${allPins.length} pins with .connection-pin class:`);
        
        allPins.forEach((pin, index) => {
            const rect = pin.getBoundingClientRect();
            console.log(`Pin ${index + 1}:`);
            console.log('  ID:', pin.id);
            console.log('  Dataset:', pin.dataset);
            console.log('  Position:', rect);
            console.log('  Visible:', rect.width > 0 && rect.height > 0);
            console.log('  Z-index:', getComputedStyle(pin).zIndex);
            console.log('  Pointer events:', getComputedStyle(pin).pointerEvents);
            console.log('  Cursor:', getComputedStyle(pin).cursor);
            console.log('  ---');
        });
        
        // Check SVG canvas
        const svg = document.querySelector('#connection-svg');
        if (svg) {
            console.log('SVG Canvas found:', svg.getBoundingClientRect());
        } else {
            console.error('SVG Canvas NOT found!');
        }
        
        // Check if JavaScript event system is working
        console.log('JavaScript globals:');
        console.log('  haywire_on_connection_created:', typeof window.haywire_on_connection_created);
        console.log('  haywire_nodeObserver:', typeof window.haywire_nodeObserver);
        console.log('  updateConnectionPath:', typeof window.updateConnectionPath);
        
        // Test simple interaction
        console.log('Testing simple pin click...');
        if (allPins.length >= 2) {
            const testPin = allPins[0];
            console.log('Simulating click on first pin...');
            testPin.click();
        }
        
        console.log('=== END PIN DEBUG ===');
        """)
    
    def debug_connections(self):
        """Debug connection system"""
        ui.notify('Debugging connection system...', type='info')
        
        ui.run_javascript("""
        console.log('=== CONNECTION DEBUG SESSION ===');
        
        // Check for connection drag system variables
        console.log('Connection drag system check:');
        
        // Test if mouse events are being captured
        let testEventCount = 0;
        const testHandler = (e) => {
            testEventCount++;
            if (testEventCount <= 5) {  // Limit spam
                console.log('Mouse event detected:', e.type, e.target.className);
            }
        };
        
        document.body.addEventListener('mousedown', testHandler, true);
        document.body.addEventListener('mousemove', testHandler, true);
        document.body.addEventListener('mouseup', testHandler, true);
        
        setTimeout(() => {
            document.body.removeEventListener('mousedown', testHandler, true);
            document.body.removeEventListener('mousemove', testHandler, true);
            document.body.removeEventListener('mouseup', testHandler, true);
            console.log('Event test complete, detected', testEventCount, 'events');
        }, 2000);
        
        console.log('Try moving your mouse for 2 seconds to test event capture...');
        console.log('=== END CONNECTION DEBUG ===');
        """)
    
    def test_simple_pin(self):
        """Create a simple test pin for debugging"""
        ui.notify('Creating test pin...', type='info')
        
        with self.zoom_container:
            test_pin = ui.element('div').props(
                'id="simple-test-pin" data-test="true"'
            ).style(
                'position: absolute; '
                'left: 50px; top: 50px; '
                'width: 40px; height: 40px; '
                'background: red; '
                'border: 4px solid yellow; '
                'border-radius: 50%; '
                'cursor: pointer; '
                'z-index: 20000;'
            )
            
            test_pin.on('click', lambda: ui.notify('Test pin clicked!', type='positive'))
            
            # Add JavaScript event test
            ui.run_javascript("""
            setTimeout(() => {
                const testPin = document.getElementById('simple-test-pin');
                if (testPin) {
                    console.log('Simple test pin created:', testPin.getBoundingClientRect());
                    testPin.addEventListener('mousedown', (e) => {
                        console.log('Simple test pin mousedown');
                        alert('Simple test pin works!');
                    });
                } else {
                    console.error('Simple test pin not found');
                }
            }, 100);
            """)
    
    def create_random_graph(self):
        """Create a random graph for testing."""
        # Get available node types from registry
        available_nodes = self.get_available_nodes()
        if not available_nodes:
            ui.notify("No node types available", type='warning')
            return
            
        # Create a few random nodes
        for i in range(random.randint(3, 6)):
            try:
                node_type = random.choice(available_nodes)
                x = random.randint(100, 800)
                y = random.randint(100, 500)
                
                node = self.node_factory.create_instance(node_type, self.graph, position=(x, y))
                node.ui_posX = x
                node.ui_posY = y
                
                if self.history_manager:
                    action = AddNodeAction(self.graph, node)
                    self.history_manager.add_action(action)
                else:
                    self.graph.add_node(node)
                
                self.canvas_manager.add_node_visual(node, (x, y))
                self.stats['nodes_created'] += 1
                
            except Exception as e:
                print(f"Error creating random node: {e}")
        
        self.update_displays()
        ui.notify(f"Random graph created!")
    
    # Configuration Methods
    def toggle_auto_grouping(self, enabled: bool):
        """Toggle auto-grouping setting."""
        if self.history_manager:
            self.undo_config.enable_auto_grouping = enabled
            ui.notify(f"Auto grouping: {'enabled' if enabled else 'disabled'}")
    
    def toggle_action_merging(self, enabled: bool):
        """Toggle action merging setting."""
        if self.history_manager:
            self.undo_config.enable_action_merging = enabled
            ui.notify(f"Action merging: {'enabled' if enabled else 'disabled'}")
    
    def set_max_actions(self, max_actions: int):
        """Set maximum number of undo actions."""
        if self.history_manager:
            self.undo_config.max_actions = max_actions
            ui.notify(f"Max undo actions set to: {max_actions}")
    
    # UI Update Methods
    def update_canvas_status(self):
        """Update canvas manager status display for current session."""
        if hasattr(self, 'current_session'):
            self.update_displays_for_session(self.current_session)
        else:
            # Fallback for backward compatibility
            if hasattr(self, 'canvas_status_container') and hasattr(self, 'canvas_manager'):
                self.canvas_status_container.clear()
                with self.canvas_status_container:
                    ui.label(f'✓ Canvas Manager Active').classes('text-green-600 text-sm')
                    ui.label(f'Visual Nodes: {len(self.canvas_manager.node_panels)}').classes('text-sm')
                    ui.label(f'Visual Connections: {len(self.canvas_manager.connection_paths)}').classes('text-sm')
    
    def update_stats_display(self):
        """Update the statistics display for current session."""
        if hasattr(self, 'current_session'):
            self.update_displays_for_session(self.current_session)
        else:
            # Fallback for backward compatibility
            if hasattr(self, 'stats_container'):
                self.stats_container.clear()
                with self.stats_container:
                    ui.label(f'Nodes Created: {self.global_stats["nodes_created"]}')
                    ui.label(f'Connections Created: {self.global_stats["edges_created"]}')
                    ui.label(f'Undo Operations: {self.global_stats["undo_operations"]}')
                    ui.label(f'Redo Operations: {self.global_stats["redo_operations"]}')
    
    def update_info_display(self):
        """Update the information display for current session."""
        if hasattr(self, 'current_session'):
            self.update_displays_for_session(self.current_session)
        else:
            # Fallback for backward compatibility  
            if hasattr(self, 'info_container'):
                self.info_container.clear()
                with self.info_container:
                    ui.label(f'Graph ID: {self.graph.graph_id}').classes('text-sm')
                    ui.label(f'Nodes: {len(self.graph.nodes)}')
                    ui.label(f'Connections: {len(self.graph.edges)}')
    
    def update_history_display(self):
        """Update the history display for current session."""
        if hasattr(self, 'current_session'):
            containers = self.current_session.get('ui_containers', {})
            if 'history_container' in containers:
                container = containers['history_container']
                container.clear()
                with container:
                    if self.history_manager:
                        ui.label(f'History Size: {len(self.history_manager.history)}').classes('text-sm')
                        ui.label(f'Current Index: {self.history_manager.current_index}').classes('text-sm')
                        if self.history_manager.history:
                            ui.label('Recent Actions:').classes('font-bold text-sm')
                            # Show last 5 actions
                            recent_actions = self.history_manager.history[-5:]
                            for i, item in enumerate(recent_actions):
                                if hasattr(item, 'description'):
                                    ui.label(f'• {item.description}').classes('text-xs pl-2')
                                else:
                                    ui.label(f'• {type(item).__name__}').classes('text-xs pl-2')
                    else:
                        ui.label('History not available').classes('text-gray-500')
        else:
            # Fallback for backward compatibility
            if hasattr(self, 'history_container'):
                self.history_container.clear()
                with self.history_container:
                    if self.history_manager:
                        ui.label(f'History Size: {len(self.history_manager.history)}').classes('text-sm')
                    else:
                        ui.label('History not available').classes('text-gray-500')
    
    def update_history_display_for_session(self, session_data):
        """Update history display for a specific session."""
        containers = session_data.get('ui_containers', {})
        if 'history_container' in containers:
            container = containers['history_container']
            container.clear()
            with container:
                if self.history_manager:
                    ui.label(f'History Size: {len(self.history_manager.history)}').classes('text-sm')
                    ui.label(f'Current Index: {self.history_manager.current_index}').classes('text-sm')
                    if self.history_manager.history:
                        ui.label('Recent Actions:').classes('font-bold text-sm')
                        # Show last 5 actions
                        recent_actions = self.history_manager.history[-5:]
                        for i, item in enumerate(recent_actions):
                            if hasattr(item, 'description'):
                                ui.label(f'• {item.description}').classes('text-xs pl-2')
                            else:
                                ui.label(f'• {type(item).__name__}').classes('text-xs pl-2')
                else:
                    ui.label('History not available').classes('text-gray-500')

    def update_selection_display(self):
        """Update selection display for current session."""
        if hasattr(self, 'current_session'):
            self.update_selection_display_for_session(self.current_session)
    
    def update_displays(self):
        """Update all displays."""
        self.update_stats_display()
        self.update_info_display()
        self.update_history_display()
        self.update_canvas_status()
        self.update_selection_display()
    
    def run(self):
        """Run the application."""
        print("Starting Enhanced Test App with Canvas Manager...")
        self.create_ui()
        ui.run(port=8082, show=True, title="Enhanced Haywire Test with Canvas Manager", reload=False)
    
    def cleanup(self):
        """Cleanup resources."""
        if self.canvas_manager:
            unregister_canvas_manager(self.canvas_manager)
            self.canvas_manager.cleanup()


def main():
    """Main entry point."""
    app = UndoRedoTestAppWithCanvasManager()
    try:
        app.run()
    finally:
        app.cleanup()


if __name__ in {"__main__", "__mp_main__"}:
    main()
