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
from nicegui import ui

# Add project paths
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Haywire imports
from haywire.ui.editor_v1.graph_canvas_manager import GraphCanvasManager
from haywire.ui.editor_v1.editor import Editor
from haywire.core.graph.graph import HaywireGraph
from haywire.undo.config import DEVELOPMENT_CONFIG
from haywire.ui.themes import ThemePalette

# DI imports  
from haywire.core.di.config import create_library_system_service

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
        
        # Get theme palette from DI
        self.theme_palette = self.library_service.get_theme_palette()
        
        # Register as observer for theme changes
        ThemePalette.register_observer(self._on_theme_changed)
        
        # Create ONE shared graph for all sessions
        self.graph = HaywireGraph("shared_graph", self.node_factory, "Shared Graph Across Sessions")
        
        # Create shared Editor instance
        self.editor = Editor(self.graph, self.history_manager, self.node_factory)
        
        # Register global change listener for app-level updates
        self.editor.add_change_callback(self._on_global_graph_change)
        
        # Global stats (shared across sessions)
        self.global_stats = {
            'nodes_created': 0,
            'edges_created': 0,
            'undo_operations': 0,
            'redo_operations': 0
        }
        
        print(f"History manager available: {self.history_manager is not None}")
        print(f"Editor created with change callbacks")
        print("Shared services configured successfully.")
    
    def _on_theme_changed(self, theme_name: str, theme):
        """Handle theme change events."""
        print(f"🎨 Theme changed to: {theme_name}")
        
        # Defer UI updates to avoid deleting elements during callbacks
        # Use timer to update after the current event completes
        ui.timer(0.1, lambda: self._deferred_theme_update(), once=True)
    
    def _deferred_theme_update(self):
        """Deferred theme update to avoid UI deletion during callbacks."""
        # Update UI for all sessions
        for session_data in self.sessions.values():
            self.update_displays_for_session(session_data)
        
        # Trigger UI refresh via canvas managers
        for session_data in self.sessions.values():
            if 'canvas_manager' in session_data and session_data['canvas_manager']:
                # Canvas manager will need to be updated to handle theme changes
                # For now, just update displays
                pass
    
    def _on_global_graph_change(self):
        """Handle global graph changes (affects all sessions)."""
        print("🌍 Global graph change detected")
        
        # Update global stats
        self.global_stats['nodes_created'] = len(self.graph.node_wrappers)
        self.global_stats['edges_created'] = len(self.graph.edges)
        
        # Update displays for all sessions
        for session_data in self.sessions.values():
            self.update_displays_for_session(session_data)
    
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
        """Create the left control panel with all information sections."""
        with ui.card().classes('w-80 overflow-auto').style('height: calc(100vh - 120px);'):
            ui.label('Controls & Information').classes('text-lg font-bold mb-4')
            
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
            
            # Installed Libraries
            with ui.expansion('Installed Libraries', icon='extension').classes('w-full'):
                with ui.column() as libraries_container:
                    self.current_session['ui_containers']['libraries_container'] = libraries_container
                    self.update_libraries_display()
            
            # Theme Selection
            with ui.expansion('Theme Selection', icon='palette').classes('w-full'):
                with ui.column() as theme_container:
                    self.current_session['ui_containers']['theme_container'] = theme_container
                    self.update_theme_display()
            
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
            
            # Create session-specific canvas manager with shared Editor
            canvas_manager = GraphCanvasManager(
                editor=self.editor,  # Pass the shared Editor instance
                node_render_factory=self.node_render_factory,
                session_id=client_id,
            )
            session_data['canvas_manager'] = canvas_manager
                        
            # IMPORTANT: Sync with existing graph data when canvas manager is first created
            canvas_manager.sync_with_graph()
            print(f"Canvas manager synced with {len(self.graph.node_wrappers)} existing nodes")
            
            # Update canvas status
            self.update_canvas_status()
        
    def on_graph_changed_from_session(self, originating_session_data):
        """Handle any graph change from any session - unified callback approach."""
        session_id = originating_session_data.get('client_id', 'unknown')
        print(f"🔄 Graph changed from session {session_id[:8]}")
        
        # Update global stats - the actual graph changes are already handled by GraphCanvasManager
        self.global_stats['nodes_created'] = len(self.graph.node_wrappers)
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
                    ui.label(f'Nodes: {len(self.graph.node_wrappers)}')
                    ui.label(f'Connections: {len(self.graph.edges)}')
                    
                    if self.history_manager:
                        ui.label(f'Can Undo: {self.editor.can_undo()}')
                        ui.label(f'Can Redo: {self.editor.can_redo()}')
            
            # Update canvas status
            if 'canvas_status_container' in containers and session_data.get('canvas_manager'):
                container = containers['canvas_status_container']
                container.clear()
                with container:
                    canvas_manager = session_data['canvas_manager']
                    ui.label(f'✓ Canvas Manager Active').classes('text-green-600 text-sm')
                    ui.label(f'Visual Nodes: {len(canvas_manager.node_panels)}').classes('text-sm')
                    ui.label(f'Visual Connections: {len(canvas_manager.connection_paths)}').classes('text-sm')
            
            # Update history display for this specific session
            self.update_history_display_for_session(session_data)
            
            # Update selection display for this specific session
            self.update_selection_display_for_session(session_data)
            
            # Update libraries display for this specific session
            self.update_libraries_display_for_session(session_data)
            
            # Update theme display for this specific session
            self.update_theme_display_for_session(session_data)
                        
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
        """Perform undo operation using Editor."""
        success = self.editor.undo()
        if success:
            self.global_stats['undo_operations'] += 1
            ui.notify("Undo performed")
        else:
            ui.notify("Nothing to undo")
    
    def redo_action(self):
        """Perform redo operation using Editor."""
        success = self.editor.redo()
        if success:
            self.global_stats['redo_operations'] += 1
            ui.notify("Redo performed")
        else:
            ui.notify("Nothing to redo")
    
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
                    ui.label(f'Nodes: {len(self.graph.node_wrappers)}')
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
    
    def update_libraries_display(self):
        """Update libraries display for current session."""
        if hasattr(self, 'current_session'):
            self.update_libraries_display_for_session(self.current_session)
    
    def update_theme_display(self):
        """Update theme display for current session."""
        if hasattr(self, 'current_session'):
            self.update_theme_display_for_session(self.current_session)
    
    def update_libraries_display_for_session(self, session_data):
        """Update libraries display for a specific session."""
        containers = session_data.get('ui_containers', {})
        if 'libraries_container' in containers:
            container = containers['libraries_container']
            container.clear()
            with container:
                if hasattr(self, 'library_service') and self.library_service:
                    library_registry = self.library_service.get_library_registry()
                    if library_registry:
                        library_names = library_registry.list_names()
                        if library_names:
                            ui.label(f'Total Libraries: {len(library_names)}').classes('text-sm font-bold')
                            
                            # Add bulk enable/disable buttons
                            with ui.row().classes('w-full justify-between gap-2 mt-2 mb-3'):
                                ui.button('Enable All', 
                                    icon='play_arrow',
                                    on_click=lambda: self.enable_all_libraries()
                                ).props('size=sm color=green').classes('flex-1')
                                ui.button('Disable All', 
                                    icon='pause',
                                    on_click=lambda: self.disable_all_libraries()
                                ).props('size=sm color=orange').classes('flex-1')
                            
                            ui.separator()
                            
                            for lib_name in sorted(library_names):
                                lib_identity = library_registry.get_library_identity(lib_name)
                                is_enabled = library_registry.is_library_enabled(lib_name)
                                
                                if lib_identity:
                                    with ui.card().classes('w-full mb-2 p-2'):
                                        with ui.row().classes('w-full items-center justify-between'):
                                            # Library info section
                                            with ui.column().classes('flex-grow'):
                                                with ui.row().classes('items-center gap-2'):
                                                    status_icon = 'check_circle' if is_enabled else 'cancel'
                                                    status_color = 'text-green-500' if is_enabled else 'text-red-500'
                                                    ui.icon(status_icon).classes(f'{status_color} text-sm')
                                                    ui.label(f'{lib_identity.label}').classes('text-sm font-medium')
                                                
                                                if lib_identity.version:
                                                    ui.label(f'v{lib_identity.version}').classes('text-xs text-gray-500')
                                                if lib_identity.description:
                                                    ui.label(lib_identity.description).classes('text-xs text-gray-600')
                                            
                                            # Control buttons section
                                            with ui.column().classes('gap-1'):
                                                if is_enabled:
                                                    ui.button('Disable', 
                                                        icon='pause',
                                                        on_click=lambda ln=lib_name: self.disable_library(ln)
                                                    ).props('size=sm color=orange')
                                                else:
                                                    ui.button('Enable', 
                                                        icon='play_arrow',
                                                        on_click=lambda ln=lib_name: self.enable_library(ln)
                                                    ).props('size=sm color=green')
                                else:
                                    with ui.row().classes('items-center gap-2'):
                                        ui.icon('error').classes('text-red-500 text-sm')
                                        ui.label(lib_name).classes('text-sm')
                        else:
                            ui.label('No libraries loaded').classes('text-gray-500')
                    else:
                        ui.label('Library registry not available').classes('text-gray-500')
                else:
                    ui.label('Library service not available').classes('text-gray-500')
    
    def update_libraries_display_for_session(self, session_data):
        """Update libraries display for a specific session."""
        containers = session_data.get('ui_containers', {})
        if 'libraries_container' in containers:
            container = containers['libraries_container']
            container.clear()
            with container:
                if hasattr(self, 'library_service') and self.library_service:
                    library_registry = self.library_service.get_library_registry()
                    if library_registry:
                        library_names = library_registry.list_names()
                        if library_names:
                            ui.label(f'Total Libraries: {len(library_names)}').classes('text-sm font-bold')
                            
                            # Add bulk enable/disable buttons
                            with ui.row().classes('w-full justify-between gap-2 mt-2 mb-3'):
                                ui.button('Enable All', 
                                    icon='play_arrow',
                                    on_click=lambda: self.enable_all_libraries()
                                ).props('size=sm color=green').classes('flex-1')
                                ui.button('Disable All', 
                                    icon='pause',
                                    on_click=lambda: self.disable_all_libraries()
                                ).props('size=sm color=orange').classes('flex-1')
                            
                            ui.separator()
                            
                            for lib_name in sorted(library_names):
                                lib_identity = library_registry.get_library_identity(lib_name)
                                is_enabled = library_registry.is_library_enabled(lib_name)
                                
                                if lib_identity:
                                    with ui.card().classes('w-full mb-2 p-2'):
                                        with ui.row().classes('w-full items-center justify-between'):
                                            # Library info section
                                            with ui.column().classes('flex-grow'):
                                                with ui.row().classes('items-center gap-2'):
                                                    status_icon = 'check_circle' if is_enabled else 'cancel'
                                                    status_color = 'text-green-500' if is_enabled else 'text-red-500'
                                                    ui.icon(status_icon).classes(f'{status_color} text-sm')
                                                    ui.label(f'{lib_identity.label}').classes('text-sm font-medium')
                                                
                                                if lib_identity.version:
                                                    ui.label(f'v{lib_identity.version}').classes('text-xs text-gray-500')
                                                if lib_identity.description:
                                                    ui.label(lib_identity.description).classes('text-xs text-gray-600')
                                            
                                            # Control buttons section
                                            with ui.column().classes('gap-1'):
                                                if is_enabled:
                                                    ui.button('Disable', 
                                                        icon='pause',
                                                        on_click=lambda ln=lib_name: self.disable_library(ln)
                                                    ).props('size=sm color=orange')
                                                else:
                                                    ui.button('Enable', 
                                                        icon='play_arrow',
                                                        on_click=lambda ln=lib_name: self.enable_library(ln)
                                                    ).props('size=sm color=green')
                                else:
                                    with ui.row().classes('items-center gap-2'):
                                        ui.icon('error').classes('text-red-500 text-sm')
                                        ui.label(lib_name).classes('text-sm')
                        else:
                            ui.label('No libraries loaded').classes('text-gray-500')
                    else:
                        ui.label('Library registry not available').classes('text-gray-500')
                else:
                    ui.label('Library service not available').classes('text-gray-500')
    
    def update_theme_display_for_session(self, session_data):
        """Update theme display for a specific session."""
        containers = session_data.get('ui_containers', {})
        if 'theme_container' in containers:
            container = containers['theme_container']
            container.clear()
            with container:
                # Get current theme info
                current_theme = ThemePalette.get_current_theme()
                current_name = ThemePalette.get_theme_name()
                current_key = ThemePalette.get_theme_key()  # Get the theme key for comparison
                
                ui.label(f'Current Theme: {current_name}').classes('text-sm font-bold mb-2')
                
                # Show theme metadata
                if current_theme.metadata.author:
                    ui.label(f'Author: {current_theme.metadata.author}').classes('text-xs text-gray-600')
                if current_theme.metadata.description:
                    ui.label(f'{current_theme.metadata.description}').classes('text-xs text-gray-500 mb-2')
                
                ui.separator().classes('my-2')
                
                # List all available themes
                available_themes = ThemePalette.list_themes()
                ui.label('Available Themes:').classes('text-sm font-bold mb-2')
                
                for theme_name in available_themes:
                    # Compare theme keys (file names), not display names
                    is_current = theme_name.lower() == current_key.lower()
                    
                    with ui.row().classes('w-full items-center justify-between mb-1'):
                        with ui.row().classes('items-center gap-2'):
                            if is_current:
                                ui.icon('check_circle').classes('text-green-500 text-sm')
                            else:
                                ui.icon('radio_button_unchecked').classes('text-gray-400 text-sm')
                            ui.label(theme_name.title()).classes('text-sm')
                        
                        if not is_current:
                            ui.button('Apply', 
                                icon='palette',
                                on_click=lambda tn=theme_name: self.switch_theme(tn)
                            ).props('size=sm color=primary')
                
                ui.separator().classes('my-2')
                
                # Reload button for TOML themes
                ui.button('Reload Current Theme', 
                    icon='refresh',
                    on_click=lambda: self.reload_theme()
                ).props('size=sm color=secondary').classes('w-full')
    
    def switch_theme(self, theme_name: str):
        """Switch to a different theme."""
        # Show notification before switching to avoid UI deletion issues
        ui.notify(f"Switching to {theme_name} theme...", type='info')
        
        # Use timer to switch theme after notification is shown
        def do_switch():
            success = ThemePalette.set_theme(theme_name)
            if success:
                print(f"✓ Successfully switched to {theme_name} theme")
            else:
                ui.notify(f"Failed to load {theme_name} theme", type='negative')
        
        ui.timer(0.05, do_switch, once=True)
    
    def reload_theme(self):
        """Reload the current theme from disk."""
        current_name = ThemePalette.get_theme_name()
        ui.notify(f"Reloading {current_name} theme...", type='info')
        
        # Use timer to reload theme after notification is shown
        def do_reload():
            success = ThemePalette.reload_current_theme()
            if success:
                print(f"✓ Successfully reloaded {current_name} theme")
            else:
                ui.notify("Failed to reload theme", type='negative')
        
        ui.timer(0.05, do_reload, once=True)
    
    def update_displays(self):
        """Update all displays."""
        self.update_stats_display()
        self.update_info_display()
        self.update_history_display()
        self.update_canvas_status()
        self.update_selection_display()
        self.update_libraries_display()
    
    # Library Management Methods
    def enable_library(self, library_id: str):
        """Enable a specific library."""
        if hasattr(self, 'library_service') and self.library_service:
            library_registry = self.library_service.get_library_registry()
            if library_registry and library_registry.enable_library(library_id):
                ui.notify(f"Library '{library_id}' enabled", type='positive')
                # Update all displays to reflect the change
                self.sync_all_sessions()
                self.library_service.print_registry_status()
            else:
                ui.notify(f"Failed to enable library '{library_id}'", type='negative')
    
    def disable_library(self, library_id: str):
        """Disable a specific library."""
        if hasattr(self, 'library_service') and self.library_service:
            library_registry = self.library_service.get_library_registry()
            if library_registry and library_registry.disable_library(library_id):
                ui.notify(f"Library '{library_id}' disabled", type='warning')
                # Update all displays to reflect the change
                self.sync_all_sessions()
                self.library_service.print_registry_status()
            else:
                ui.notify(f"Failed to disable library '{library_id}'", type='negative')
    
    def enable_all_libraries(self):
        """Enable all libraries."""
        if hasattr(self, 'library_service') and self.library_service:
            library_registry = self.library_service.get_library_registry()
            if library_registry:
                library_registry.enable_all_libraries()
                ui.notify("All libraries enabled", type='positive')
                # Update all displays to reflect the change
                self.sync_all_sessions()
                self.library_service.print_registry_status()
    
    def disable_all_libraries(self):
        """Disable all libraries."""
        if hasattr(self, 'library_service') and self.library_service:
            library_registry = self.library_service.get_library_registry()
            if library_registry:
                library_names = library_registry.list_names()
                for lib_name in library_names:
                    library_registry.disable_library(lib_name)
                ui.notify("All libraries disabled", type='warning')
                # Update all displays to reflect the change
                self.sync_all_sessions()
                self.library_service.print_registry_status()
    
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
