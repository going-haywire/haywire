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
from haywire.ui.editor_v1.graph_canvas_manager import GraphCanvasManager
from haywire.core.graph.graph import HaywireGraph
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
            
            # Create session-specific canvas manager - it will create its own zoom container
            

            """             
            canvas_manager = GraphCanvasManager(
                graph=self.graph,  # Use shared graph
                node_render_factory=self.node_render_factory,  # Use shared render factory
                history_manager=self.history_manager,  # Pass the shared history manager
                node_factory=self.node_factory,  # Pass the node factory for context node creation
                available_nodes=self.get_available_nodes(),  # Pass available nodes for context menu
                on_graph_changed=lambda: self.on_graph_changed_from_session(session_data),
                session_id=client_id,
            )
            session_data['canvas_manager'] = canvas_manager
            """       
                        
            # IMPORTANT: Sync with existing graph data when canvas manager is first created
            #canvas_manager.sync_with_graph()
            print(f"Canvas manager synced with {len(self.graph.nodes)} existing nodes")
            
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
        
    def on_graph_changed_from_session(self, originating_session_data):
        """Handle any graph change from any session - unified callback approach."""
        session_id = originating_session_data.get('client_id', 'unknown')
        print(f"🔄 Graph changed from session {session_id[:8]}")
        
        # Update global stats - the actual graph changes are already handled by GraphCanvasManager
        self.global_stats['nodes_created'] = len(self.graph.nodes)
        self.global_stats['edges_created'] = len(self.graph.edges)
        
        # Sync ALL sessions (including the originating one for consistency)
        self.sync_all_sessions()
        
        # Update displays for all sessions
        for session_data in self.sessions.values():
            self.update_displays_for_session(session_data)
    
    def on_pan_change_for_specific_session(self, session_data, pan_x, pan_y):
        """Handle pan change events for specific session.""" 
        self.update_displays_for_session(session_data)
            
            
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
                    canvas_manager = session_data['canvas_manager']
                    ui.label(f'✓ Canvas Manager Active').classes('text-green-600 text-sm')
                    ui.label(f'Visual Nodes: {len(canvas_manager.node_panels)}').classes('text-sm')
                    ui.label(f'Visual Connections: {len(canvas_manager.connection_paths)}').classes('text-sm')
                    ui.label(f'Zoom: {canvas_manager.current_zoom:.2f}x').classes('text-sm')
                    ui.label(f'Pan: ({canvas_manager.pan_x:.0f}, {canvas_manager.pan_y:.0f})').classes('text-sm')
            
            # Update history display for this specific session
            self.update_history_display_for_session(session_data)
            
            # Update selection display for this specific session
            self.update_selection_display_for_session(session_data)
                        
        except Exception as e:
            print(f"Error updating displays for session: {e}")
    
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
                    ui.label(f'Zoom: {self.canvas_manager.current_zoom:.2f}x').classes('text-sm')
                    ui.label(f'Pan: ({self.canvas_manager.pan_x:.0f}, {self.canvas_manager.pan_y:.0f})').classes('text-sm')
    
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
