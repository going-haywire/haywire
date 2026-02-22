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

import logging
import os
import traceback
from pathlib import Path
from nicegui import ui, app

# Haywire imports
from haywire.core.graph.editor import Editor
from haywire.core.graph.base import BaseGraph
from haywire.core.graph.types import ValidationResult
from haywire.core.undo.config import DEVELOPMENT_CONFIG
from haywire.core.graph.utils.graph_to_python import graph_to_python_script

from haywire.ui.console_bridge import ConsoleBridge
from haywire.ui.editor.graph_canvas_manager import GraphCanvasManager
from haywire.core.execution.interpreter_loop_manager import InterpreterLoopManager
from haywire.ui.themes import ThemePalette

# Execution imports
from haywire.core.execution import Interpreter

# DI imports  
from haywire.core.di.config import create_library_system_service, set_library_system, set_global_injector

class HaywireApp:
    """Main Haywire application with node editor UI."""

    def __init__(self, workspace_root: str = None):
        self.workspace_root = workspace_root or os.getcwd()
        print(f"Haywire workspace: {self.workspace_root}")
        print("Setting up Haywire application...")
        
        # Initialize library system service (shared across all sessions)
        self.setup_library_system()
        
        # Shared data across all sessions
        self.setup_shared_services()
        
        # Session-specific UI state (client_id -> session_data)
        self.sessions = {}
        
        # Track shutdown state
        self._is_shutting_down = False

        # Register lifecycle hooks
        app.on_disconnect(self.on_disconnect)
        app.on_shutdown(self.on_app_shutdown)

    def on_app_shutdown(self):
        """
        Handle application shutdown - cleanup all resources.
        
        Called by NiceGUI when the application is stopping.

        The shutdown sequence is ordered to prevent errors:

        | Order | Component | Reason |
        |-------|-----------|--------|
        | 1 | Interpreter loop | Stop generating new events |
        | 2 | Sessions | Clean up UI before removing subscriptions |
        | 3 | Graph subscriptions | No more callbacks after this |
        | 4 | Theme observer | Prevent callbacks to deleted UI |
        | 5 | Console bridge | Stop polling timer |
        | 6 | Interpreter | Final cleanup of execution resources |
        | 7 | Library system | Last, since other components may depend on it |        

        """
        if self._is_shutting_down:
            return
        
        self._is_shutting_down = True
        print("🔧 Application shutdown initiated...")
        
        # 1. Stop interpreter loop first (stops generating new events)
        if self.loop_manager and self.loop_manager.is_running:
            print("  Stopping interpreter loop...")
            self.stop_interpreter()
        
        # 2. Clean up all sessions
        print(f"  Cleaning up {len(self.sessions)} sessions...")
        session_ids = list(self.sessions.keys())
        for client_id in session_ids:
            try:
                self._cleanup_session(client_id)
            except Exception as e:
                print(f"  Error cleaning up session {client_id[:8]}: {e}")
        
        # 3. Unsubscribe from graph validation (app-level subscription)
        print("  Unsubscribing from graph validation...")
        try:
            self.graph.unsubscribe_from_validation(self._on_global_graph_change)
        except Exception as e:
            print(f"  Error unsubscribing from validation: {e}")
        
        # 4. Unregister theme observer
        print("  Unregistering theme observer...")
        try:
            ThemePalette.unregister_observer(self._on_theme_changed)
        except Exception as e:
            print(f"  Error unregistering theme observer: {e}")
        
        # 5. Clean up console bridge (all timers cleaned via session cleanup)
        print("  Cleaning up console bridge...")
        try:
            from haywire.ui.console_bridge import ConsoleBridge
            bridge = ConsoleBridge.get_instance()
            # Clear any remaining log elements (timers already cancelled in session cleanup)
            bridge.log_elements.clear()
            bridge.clear_history()
        except Exception as e:
            print(f"  Error cleaning up console bridge: {e}")
        
        # 6. Shutdown interpreter
        print("  Shutting down interpreter...")
        try:
            if self.interpreter:
                self.interpreter.shutdown()
        except Exception as e:
            print(f"  Error shutting down interpreter: {e}")
        
        # 7. Cleanup library system
        print("  Cleaning up library system...")
        try:
            if hasattr(self.library_service, 'cleanup'):
                self.library_service.cleanup()
        except Exception as e:
            print(f"  Error cleaning up library system: {e}")
        
        print("✅ Application shutdown complete")

    def _cleanup_session(self, client_id: str):
        """
        Clean up a single session's resources.
        
        Args:
            client_id: The client ID to clean up
        """
        if client_id not in self.sessions:
            return
        
        session_data = self.sessions[client_id]
        print(f"    Cleaning up session {client_id[:8]}...")
        
        # Clean up canvas manager
        canvas_manager = session_data.get('canvas_manager')
        if canvas_manager:
            try:
                canvas_manager.cleanup()
            except Exception as e:
                print(f"    Error cleaning up canvas manager: {e}")
        
        # Cancel interpreter update timer
        interpreter_timer = session_data.get('interpreter_timer')
        if interpreter_timer:
            try:
                interpreter_timer.cancel()
            except Exception as e:
                print(f"    Error canceling interpreter timer: {e}")
        
        # Clean up console log and timer
        console_log = session_data.get('console_log')
        console_timer = session_data.get('console_timer')
        if console_log:
            try:
                from haywire.ui.console_bridge import ConsoleBridge
                bridge = ConsoleBridge.get_instance()
                bridge.unregister_log(console_log)  # This will also cancel the timer
            except Exception as e:
                print(f"    Error unregistering console log: {e}")
        elif console_timer:
            # If we only have the timer reference, cancel it directly
            try:
                console_timer.cancel()
            except Exception as e:
                print(f"    Error canceling console timer: {e}")
        
        # Clear UI containers - skip if shutting down (clients already deleted)
        if not self._is_shutting_down:
            containers = session_data.get('ui_containers', {})
            for name, container in containers.items():
                try:
                    container.clear()
                except Exception as e:
                    pass  # Client likely deleted
        
        # Remove from sessions dict
        del self.sessions[client_id]
        
    def on_disconnect(self, client):
        """
        Handle client disconnect and clean up session data.
        
        Called by NiceGUI when a client disconnects.
        """
        # Skip if we're in full shutdown mode
        if self._is_shutting_down:
            return
        
        client_id = getattr(client, 'id', None)
        if client_id and client_id in self.sessions:
            print(f"Client disconnected: {client_id[:8]}")
            self._cleanup_session(client_id)
            print(f"Session {client_id[:8]} cleaned up")
            
    def get_session_data(self):
        """Get or create session-specific data for current client."""
        from nicegui import context
        
        # Use NiceGUI's client context to identify unique sessions
        client_id = context.client.id if context.client else 'default'
        
        if client_id not in self.sessions:
            print(f"Creating new session for client: {client_id}")
            session_data = self.create_session_data()
            # Store client reference for later context use
            session_data['client'] = context.client
            self.sessions[client_id] = session_data
        
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
        self.adapter_factory = self.library_service.get_adapter_factory()
        self.history_manager = self.library_service.get_history_manager()
        
        # Create interpreter and loop manager (shared)
        self.interpreter = Interpreter()
        self.loop_manager = InterpreterLoopManager(
            interpreter=self.interpreter,
            target_fps=60.0
        )

        
        # Get theme palette from DI
        self.theme_palette = self.library_service.get_theme_palette()
        
        # Register as observer for theme changes
        ThemePalette.register_observer(self._on_theme_changed)
        
        # Create ONE shared graph for all sessions
        self.graph = BaseGraph(
            "shared_graph", 
            "Shared Graph Across Sessions"
        )
        
        # Register global change listener for app-level updates
        self.graph.subscribe_to_validation(self._on_global_graph_change)

        # Create shared Editor instance (graph-managed pattern)
        self.editor = Editor(self.graph)
                
        # Global stats (shared across sessions)
        self.global_stats = {
            'nodes_created': 0,
            'edges_created': 0,
            'undo_operations': 0,
            'redo_operations': 0
        }
        
        # Create library manager for runtime install/uninstall
        from .library_manager import LibraryManager
        library_registry = self.library_service.get_library_registry()
        self.library_manager = LibraryManager(
            library_registry,
            project_dir=self.workspace_root,
        )
        # Apply persisted disabled state from project config
        self.library_manager.apply_persisted_state()

        print(f"History manager available: {self.history_manager is not None}")
        print("Editor created with change callbacks")
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
    
    def _on_global_graph_change(self, result: ValidationResult):
        """
        Handle global graph changes from ValidationManager.
        Thread sync from graph thread to main UI thread. 
        """
        # first stop the interpreter 
        self._on_graph_validation_for_interpreter(result)

        # Schedule UI update for each active client session
        for client_id, session_data in list(self.sessions.items()):
            client = session_data.get('client')
            if client:
                try:
                    # Update global stats (shared)
                    self.global_stats['nodes_created'] = len(self.graph.node_wrappers)
                    self.global_stats['edges_created'] = len(self.graph.edge_wrappers)
                    
                    # Update canvas manager for this session
                    canvas_manager: GraphCanvasManager = session_data.get('canvas_manager')
                    if canvas_manager:
                        try:
                            canvas_manager._on_validated(result)
                        except Exception as e:
                            print(f"Error updating canvas: {e}")
                    
                    # Update displays for this session
                    self.update_displays_for_session(session_data)
                except Exception as e:
                    print(
                        f"Error scheduling graph change for "
                        f"session {client_id[:8]}: {e}"
                    )
                    
    def setup_library_system(self):
        """Initialize the library system service."""
        # Store undo config for UI access
        self.undo_config = DEVELOPMENT_CONFIG
        
        # Create and initialize the library system service with undo support
        # Determine library paths from workspace
        library_paths = []
        workspace_libs = os.path.join(self.workspace_root, 'libraries')
        if os.path.isdir(workspace_libs):
            library_paths.append(workspace_libs)

        self.library_service = create_library_system_service(
            project_root=self.workspace_root,
            library_paths=library_paths if library_paths else None,
            enable_file_watching=True,
            watch_settings=False,
            undo_config=self.undo_config
        )
        
        # Set global helpers
        set_library_system(self.library_service)
        set_global_injector(self.library_service.injector)
        
        print("Enhanced DI system initialized successfully.")
            
    def setup_services(self):
        """Get all required services from the library system."""
        # Services will now be accessed per session
        # Remove the old global service setup
        pass


    def create_ui(self):
        """Create the main UI."""
        # Library management page
        @ui.page('/libraries', title="Library Manager")
        def libraries_page():
            from .library_manager_ui import LibraryManagerPage
            marketplace_path = Path(self.workspace_root) / '.haywire' / 'marketplace.toml'
            page = LibraryManagerPage(
                self.library_manager,
                marketplace_path=str(marketplace_path) if marketplace_path.exists() else None,
                node_registry=self.node_registry,
                widget_registry=self.library_service.get_widget_registry(),
                type_registry=self.library_service.get_type_registry(),
                adapter_registry=self.library_service.get_adapter_registry(),
                renderer_registry=self.library_service.get_renderer_registry(),
            )
            page.create_page()

        @ui.page('/', title="Enhanced Haywire Test App with Canvas Manager")
        def main_page():
            # Get session-specific data
            session_data, client_id = self.get_session_data()
            
            # Store current session in UI context
            self.current_session = session_data
            self.current_client_id = client_id
            
            print(f"Creating UI for session: {client_id[:8]}")
            
            self.create_header()
            
            with ui.row().classes('w-full flex-grow gap-4 p-4').style(
                'height: calc(100vh - 80px);'
            ):
                self.create_left_panel()
                self.create_main_editor()
            
            # Set up periodic UI update timer for interpreter stats
            # This runs on the main thread and safely updates UI
            session_data['interpreter_timer'] = ui.timer(
                    0.1,  # Update every 100ms
                    lambda: self.update_interpreter_display(),
                    active=True
                )

    def create_header(self):
        """Create the application header with main controls."""
        with ui.header().classes('bg-blue-600 text-white px-4 py-2'):
            with ui.row().classes('w-full justify-between items-center'):
                ui.label('Enhanced Haywire Test App').classes('text-xl font-bold')
                
                with ui.row().classes('gap-2'):
                    ui.button('Save', on_click=self.save_graph, icon='save')
                    ui.button(
                        'Export to Python',
                        on_click=self.export_to_python,
                        icon='code'
                    )
                    ui.button('Load', on_click=self.load_graph, icon='folder_open')
                    ui.button('Clear', on_click=self.clear_graph, icon='delete')
                    
                    ui.separator().props('vertical')
                    
                    ui.button('Undo', on_click=self.undo_action, icon='undo')
                    ui.button('Redo', on_click=self.redo_action, icon='redo')

                    ui.separator().props('vertical')

                    ui.button(
                        'Libraries',
                        icon='extension',
                        on_click=lambda: ui.navigate.to('/libraries'),
                    )
                    
                    ui.separator().props('vertical')
                    
                    # Interpreter controls
                    ui.button(
                        'Play',
                        on_click=self.start_interpreter,
                        icon='play_arrow',
                        color='green'
                    ).bind_visibility_from(
                        self,
                        'loop_manager',
                        backward=lambda x: not (x and x.is_running)
                    )
                    
                    ui.button(
                        'Stop',
                        on_click=self.stop_interpreter,
                        icon='stop',
                        color='red'
                    ).bind_visibility_from(
                        self,
                        'loop_manager',
                        backward=lambda x: x and x.is_running
                    )
                    
                    ui.number(
                        label='FPS',
                        value=60,
                        min=1,
                        max=120,
                        step=1,
                        on_change=lambda e: self.set_target_fps(e.value)
                    ).classes('w-24').props('dense')
                        
    def create_left_panel(self):
        """Create the left control panel with all information sections."""
        with ui.card().classes('w-80 overflow-auto').style('height: calc(100vh - 120px);'):
            ui.label('Controls & Information').classes('text-lg font-bold mb-4')
            
            # Canvas Manager Status
            with ui.expansion(
                'Canvas Manager Status',
                icon='dashboard'
            ).classes('w-full'):
                with ui.column() as canvas_status_container:
                    # Store reference in session data
                    self.current_session['ui_containers'][
                        'canvas_status_container'
                    ] = canvas_status_container
                    ui.label(
                        'Canvas Manager: Initializing...'
                    ).classes('text-sm text-gray-600')
            
            # Interpreter Status
            with ui.expansion(
                'Interpreter Status',
                icon='play_circle'
            ).classes('w-full'):
                with ui.column() as interpreter_container:
                    self.current_session['ui_containers'][
                        'interpreter_container'
                    ] = interpreter_container
                    self.update_interpreter_display()
                                                
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
                    self.current_session['ui_containers'][
                        'selection_container'
                    ] = selection_container
                    ui.label('No nodes selected').classes('text-gray-500')
            
            # Installed Libraries
            with ui.expansion('Installed Libraries', icon='extension').classes('w-full'):
                with ui.column() as libraries_container:
                    self.current_session['ui_containers'][
                        'libraries_container'
                    ] = libraries_container
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

            with ui.expansion('Console Output', icon='terminal').classes('w-full').props('default-opened'):
                console_log = ui.log(max_lines=200).classes('w-full h-64 font-mono text-xs')
                
                # Register with bridge and create timer in current client context
                bridge = ConsoleBridge.get_instance()
                console_timer = bridge.register_log_with_polling(console_log, interval=0.1)
                
                # Store references for cleanup
                self.current_session['console_log'] = console_log
                self.current_session['console_timer'] = console_timer
                
                with ui.row().classes('w-full gap-2 mt-2'):
                    ui.button('Clear', icon='delete', 
                        on_click=lambda: console_log.clear()
                    ).props('size=sm')
                    ui.button('Copy', icon='content_copy',
                        on_click=lambda: copy_from_bridge()
                    ).props('size=sm')

                    def copy_from_bridge():
                        bridge = ConsoleBridge.get_instance()
                        text = bridge.get_history_text()
                        if text:
                            ui.run_javascript(f'navigator.clipboard.writeText({repr(text)})')
                            ui.notify(f'Copied {len(text)} characters', type='positive')
                        else:
                            ui.notify('Console is empty', type='warning')

    def create_main_editor(self):
        """Create the main node editor with GraphCanvasManager."""
        with ui.card().classes('flex-grow').style(
            'min-width: 600px; height: calc(100vh - 120px);'
        ):
            ui.label(
                f'Node Editor - Session {self.current_client_id[:8]}'
            ).classes('text-lg font-bold mb-2')
            
            # Capture current session data for callbacks
            session_data = self.current_session
            client_id = self.current_client_id
            
            # Create session-specific canvas manager - it will create its own zoom container
            
            # Create session-specific canvas manager with shared Editor
            canvas_manager = GraphCanvasManager(
                editor=self.editor,  # Pass the shared Editor instance
                node_render_factory=self.node_render_factory,
                node_factory=self.node_factory,
                session_id=client_id[:8],
            )
            session_data['canvas_manager'] = canvas_manager
                        
            # IMPORTANT: Sync with existing graph data when canvas manager is first created
            canvas_manager.sync_with_graph()
            
            # Update canvas status
            self.update_canvas_status()
        
    def on_graph_changed_from_session(self, originating_session_data):
        """Handle any graph change from any session - unified callback approach."""
        session_id = originating_session_data.get('client_id', 'unknown')
        print(f"🔄 Graph changed from session {session_id[:8]}")
        
        # Update global stats - the actual graph changes are already handled by GraphCanvasManager
        self.global_stats['nodes_created'] = len(self.graph.node_wrappers)
        self.global_stats['edges_created'] = len(self.graph.edge_wrappers)
        
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
            canvas_manager = session_data.get('canvas_manager')
            if not canvas_manager:
                continue
                
            try:
                # Check if canvas manager is still valid before syncing
                if hasattr(canvas_manager, 'canvas_vue'):
                    # Attempt a safe operation to check if client is alive
                    _ = canvas_manager.canvas_vue.client
                
                print(f"Syncing session {client_id[:8]} with graph data")
                canvas_manager.sync_with_graph()
                
                # Force update displays for each session
                self.update_displays_for_session(session_data)
                
                print(f"Synced graph data for session {client_id[:8]}")
                
            except RuntimeError as e:
                if "client this element belongs to has been deleted" in str(e):
                    print(
                        f"Client {client_id[:8]} disconnected, "
                        "marking for cleanup"
                    )
                    sessions_to_remove.append(client_id)
                else:
                    print(f"Runtime error syncing session {client_id[:8]}: {e}")
            except Exception as e:
                print(f"Error syncing session {client_id[:8]}: {e}")
                # Consider marking for removal if errors persist
                sessions_to_remove.append(client_id)
        
        # Clean up disconnected sessions
        for client_id in sessions_to_remove:
            print(f"Force removing disconnected session: {client_id[:8]}")
            if client_id in self.sessions:
                # Call on_disconnect logic manually
                self.on_disconnect(type('obj', (), {'id': client_id})())
    
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
                    ui.label(f'Connections: {len(self.graph.edge_wrappers)}')
                    
                    if self.history_manager:
                        ui.label(f'Can Undo: {self.editor.can_undo()}')
                        ui.label(f'Can Redo: {self.editor.can_redo()}')
            
            # Update canvas status
            if 'canvas_status_container' in containers and session_data.get('canvas_manager'):
                container = containers['canvas_status_container']
                container.clear()
                with container:
                    canvas_manager = session_data['canvas_manager']
                    ui.label('✓ Canvas Manager Active').classes('text-green-600 text-sm')
                    ui.label(
                        f'Visual Nodes: {len(canvas_manager.node_panels)}'
                    ).classes('text-sm')
                    ui.label(
                        f'Visual Connections: {len(canvas_manager.connection_paths)}'
                    ).classes('text-sm')
            
            # Update history display for this specific session
            self.update_history_display_for_session(session_data)
            
            # Update selection display for this specific session
            self.update_selection_display_for_session(session_data)
            
            # Update libraries display for this specific session
            self.update_libraries_display_for_session(session_data)
            
            # Update theme display for this specific session
            self.update_theme_display_for_session(session_data)
            
            # Update interpreter display for this specific session
            self.update_interpreter_display_for_session(session_data)
                        
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
                        ui.label(
                            f'Selected: {len(selected_nodes)} nodes, '
                            f'{len(selected_connections)} connections'
                        ).classes('font-bold')
                        
                        # Show first 5 selected nodes
                        for node_id in list(selected_nodes)[:5]:
                            ui.label(f'• Node: {node_id}').classes('text-xs pl-2')
                        if len(selected_nodes) > 5:
                            ui.label(
                                f'... and {len(selected_nodes) - 5} more nodes'
                            ).classes('text-xs pl-2 text-gray-500')
                        
                        # Show first 3 selected connections
                        for connection_id in list(selected_connections)[:3]:
                            ui.label(
                                f'• Connection: {connection_id[:30]}...'
                            ).classes('text-xs pl-2')
                        if len(selected_connections) > 3:
                            ui.label(
                                f'... and {len(selected_connections) - 3} more connections'
                            ).classes('text-xs pl-2 text-gray-500')
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
    
    # Interpreter Methods
    def start_interpreter(self):
        """Start the interpreter loop."""
        # Validate graph first
        errors = self.graph.validate()
        
        if errors:
            error_summary = '\n'.join(errors[:3])  # Show first 3 errors
            if len(errors) > 3:
                error_summary += f'\n... and {len(errors) - 3} more errors'
            
            ui.notify(
                f'Cannot start - graph has {len(errors)} error(s)',
                type='negative',
                position='top'
            )
            print(f"Graph validation errors:\n{error_summary}")
            return
        
        # Load current graph (triggers assembly)
        try:
            # TODO: This code makes the graph super slow - And I dont know why:
            for _, wrapper in self.graph.node_wrappers.items():
                wrapper.clear_runtime_errors()
            # shen the _clear_runtime_errors is called to redraw the nodes, it 
            # becomes super slow.
            
            self.graph.force_validation()

            self.interpreter.load_graph(self.graph)
        except Exception as e:
            ui.notify(
                f'Failed to load graph: {str(e)}',
                type='negative',
                position='top'
            )
            print(f"Error loading graph: {e}")
            traceback.print_exc()
            return
        
        # Start loop
        self.loop_manager.start()
        
        ui.notify("Interpreter started", type='positive', position='top')
        print("Interpreter loop started")
    
    def stop_interpreter(self):
        """Stop the interpreter loop."""
        self.loop_manager.stop()
        
        # Wait for all flows to complete
        try:
            self.interpreter.wait_all(timeout=2.0)
        except Exception as e:
            print(f"Error waiting for flows: {e}")
        
        print("Interpreter loop stopped")

    def set_target_fps(self, fps: float):
        """Update target framerate."""
        if fps > 0:
            self.loop_manager.set_target_fps(fps)
            print(f"Target FPS set to {fps}")
    
    def _on_graph_validation_for_interpreter(self, result: ValidationResult):
        """
        Handle graph validation changes for interpreter.
        
        When graph changes require reassembly (like hot reload), stop the
        interpreter. User must press Play again to validate/reassemble/restart.
        """
        # Check if interpreter is running
        if not self.loop_manager or not self.loop_manager.is_running:
            return
        
        # Check if changes require reassembly
        if (
            result.has_changes() and result.graph is not None
            and result.graph.requires_graph_reassembly()
        ):            
            # Stop the interpreter - user must manually restart
            self.stop_interpreter()
            
    
    def update_interpreter_display(self):
        """Update interpreter status display for current session."""
        if not hasattr(self, 'current_session'):
            return
        
        containers = self.current_session.get('ui_containers', {})
        if 'interpreter_container' not in containers:
            return
        
        container = containers['interpreter_container']
        container.clear()
        
        with container:
            if self.loop_manager:
                stats = self.loop_manager.get_stats()
                
                if stats['is_running']:
                    ui.label('✓ Running').classes('text-green-600 font-bold')
                else:
                    ui.label('○ Stopped').classes('text-gray-500')
                
                ui.label(
                    f'Target FPS: {stats["target_fps"]:.1f}'
                ).classes('text-sm')
                ui.label(
                    f'Actual FPS: {stats["actual_fps"]:.1f}'
                ).classes('text-sm')
                ui.label(
                    f'Frames: {stats["frame_count"]}'
                ).classes('text-sm')
            else:
                ui.label('Not initialized').classes('text-gray-500')
    
    # File I/O Methods
    def save_graph(self):
        """Save the graph to a JSON file."""
        import os
        from datetime import datetime
        
        # Create saves directory if it doesn't exist
        saves_dir = os.path.join(self.workspace_root, 'saves')
        os.makedirs(saves_dir, exist_ok=True)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"graph_{timestamp}.json"
        filepath = os.path.join(saves_dir, filename)
        
        # Save the graph
        if self.graph.save_to_file(filepath, include_data=True):
            ui.notify(
                f"Graph saved successfully: {filename}", 
                type='positive',
                position='top'
            )
            print(f"Graph saved to: {filepath}")
        else:
            ui.notify(
                "Failed to save graph",
                type='negative',
                position='top'
            )
    
    def export_to_python(self):
        """Export the graph to a Python script."""
        import os
        from datetime import datetime
        
        # Create saves directory if it doesn't exist
        saves_dir = os.path.join(self.workspace_root, 'saves')
        os.makedirs(saves_dir, exist_ok=True)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"graph_{timestamp}.py"
        filepath = os.path.join(saves_dir, filename)
        
        try:
            # Generate Python script from graph
            python_code = graph_to_python_script(self.graph)
            
            # Write to file
            with open(filepath, 'w') as f:
                f.write(python_code)
            
            ui.notify(
                f"Graph exported to {filename}",
                type='positive',
                position='top'
            )
            print(f"Graph exported to {filepath}")
        except Exception as e:
            ui.notify(
                f"Failed to export graph: {str(e)}",
                type='negative',
                position='top'
            )
            print(f"Export error: {e}")
            traceback.print_exc()
            
    
    def load_graph(self):
        """Load a graph from a JSON file."""
        import os
        
        saves_dir = os.path.join(self.workspace_root, 'saves')
        
        # Check if saves directory exists
        if not os.path.exists(saves_dir):
            ui.notify(
                "No saved graphs found",
                type='warning',
                position='top'
            )
            return
        
        # Get list of saved graphs
        graph_files = [
            f for f in os.listdir(saves_dir) 
            if f.endswith('.json') and f.startswith('graph_')
        ]
        
        if not graph_files:
            ui.notify(
                "No saved graphs found",
                type='warning',
                position='top'
            )
            return
        
        # Sort by modification time (newest first)
        graph_files.sort(
            key=lambda f: os.path.getmtime(os.path.join(saves_dir, f)),
            reverse=True
        )
        
        # Show dialog to select file
        with ui.dialog() as dialog, ui.card():
            ui.label('Select a graph to load:').classes('text-lg font-bold mb-4')
            
            with ui.column().classes('w-96 gap-2'):
                for filename in graph_files:
                    filepath = os.path.join(saves_dir, filename)
                    mtime = os.path.getmtime(filepath)
                    from datetime import datetime
                    mtime_str = datetime.fromtimestamp(mtime).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                    
                    with ui.row().classes('w-full items-center gap-2'):
                        ui.button(
                            filename,
                            on_click=lambda f=filepath, d=dialog: (
                                self._do_load_graph(f), d.close()
                            )
                        ).classes('flex-grow')
                        ui.label(mtime_str).classes('text-xs text-gray-500')
            
            with ui.row().classes('w-full justify-end mt-4'):
                ui.button('Cancel', on_click=dialog.close)
        
        dialog.open()
    
    def _do_load_graph(self, filepath: str):
        """Actually load the graph file."""
        if self.graph.load_from_file(filepath):
            ui.notify(
                f"Graph loaded successfully",
                type='positive',
                position='top'
            )
            print(f"Graph loaded from: {filepath}")
            # Sync all sessions with the newly loaded graph
            self.sync_all_sessions()
        else:
            ui.notify(
                "Failed to load graph",
                type='negative',
                position='top'
            )
    
    def clear_graph(self):
        """Clear the entire graph after confirmation."""
        with ui.dialog() as dialog, ui.card():
            ui.label('Clear entire graph?').classes('text-lg font-bold')
            ui.label(
                'This will remove all nodes and connections. This cannot be undone.'
            ).classes('text-gray-600 mb-4')
            
            with ui.row().classes('w-full justify-end gap-2'):
                ui.button('Cancel', on_click=dialog.close)
                ui.button(
                    'Clear Graph',
                    on_click=lambda: (self._do_clear_graph(), dialog.close())
                ).props('color=negative')
        
        dialog.open()
    
    def _do_clear_graph(self):
        """Clears the graph and undo History"""
        self.graph.clear()
        # clear also all undo history and references it holds
        self.history_manager.clear()
        ui.notify("Graph cleared", type='info', position='top')
        # Sync all sessions
        self.sync_all_sessions()
    
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
                    ui.label('✓ Canvas Manager Active').classes('text-green-600 text-sm')
                    ui.label(
                        f'Visual Nodes: {len(self.canvas_manager.node_panels)}'
                    ).classes('text-sm')
                    ui.label(
                        f'Visual Connections: {len(self.canvas_manager.connection_paths)}'
                    ).classes('text-sm')
                    ui.label(
                        f'Zoom: {self.canvas_manager.current_zoom:.2f}x'
                    ).classes('text-sm')
                    ui.label(
                        f'Pan: ({self.canvas_manager.pan_x:.0f}, '
                        f'{self.canvas_manager.pan_y:.0f})'
                    ).classes('text-sm')
    
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
                    ui.label(f'Connections: {len(self.graph.edge_wrappers)}')
    
    def update_history_display(self):
        """Update the history display for current session."""
        if hasattr(self, 'current_session'):
            containers = self.current_session.get('ui_containers', {})
            if 'history_container' in containers:
                container = containers['history_container']
                container.clear()
                with container:
                    if self.history_manager:
                        ui.label(
                            f'History Size: {len(self.history_manager.history)}'
                        ).classes('text-sm')
                        ui.label(
                            f'Current Index: {self.history_manager.current_index}'
                        ).classes('text-sm')
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
                        ui.label(
                            f'History Size: {len(self.history_manager.history)}'
                        ).classes('text-sm')
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
                    ui.label(
                        f'History Size: {len(self.history_manager.history)}'
                    ).classes('text-sm')
                    ui.label(
                        f'Current Index: {self.history_manager.current_index}'
                    ).classes('text-sm')
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
                            ui.label(
                                f'Total Libraries: {len(library_names)}'
                            ).classes('text-sm font-bold')
                            
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
                                        with ui.row().classes(
                                            'w-full items-center justify-between'
                                        ):
                                            # Library info section
                                            with ui.column().classes('flex-grow'):
                                                with ui.row().classes('items-center gap-2'):
                                                    status_icon = (
                                                        'check_circle' if is_enabled else 'cancel'
                                                    )
                                                    status_color = (
                                                        'text-green-500' 
                                                        if is_enabled 
                                                        else 'text-red-500'
                                                    )
                                                    ui.icon(status_icon).classes(
                                                        f'{status_color} text-sm'
                                                    )
                                                    ui.label(
                                                        f'{lib_identity.label}'
                                                    ).classes('text-sm font-medium')
                                                
                                                if lib_identity.version:
                                                    ui.label(
                                                        f'v{lib_identity.version}'
                                                    ).classes('text-xs text-gray-500')
                                                if lib_identity.description:
                                                    ui.label(
                                                        lib_identity.description
                                                    ).classes('text-xs text-gray-600')
                                            
                                            # Control buttons section
                                            with ui.column().classes('gap-1'):
                                                if is_enabled:
                                                    ui.button(
                                                        'Disable', 
                                                        icon='pause',
                                                        on_click=lambda ln=lib_name: (
                                                            self.disable_library(ln)
                                                        )
                                                    ).props('size=sm color=orange')
                                                else:
                                                    ui.button(
                                                        'Enable', 
                                                        icon='play_arrow',
                                                        on_click=lambda ln=lib_name: (
                                                            self.enable_library(ln)
                                                        )
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
                    ui.label(
                        f'Author: {current_theme.metadata.author}'
                    ).classes('text-xs text-gray-600')
                if current_theme.metadata.description:
                    ui.label(
                        f'{current_theme.metadata.description}'
                    ).classes('text-xs text-gray-500 mb-2')
                
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
    
    def update_interpreter_display_for_session(self, session_data):
        """Update interpreter status display for a specific session."""
        containers = session_data.get('ui_containers', {})
        if 'interpreter_container' not in containers:
            return
        
        container = containers['interpreter_container']
        container.clear()
        
        with container:
            if self.loop_manager:
                stats = self.loop_manager.get_stats()
                
                # Status indicator
                if stats['is_running']:
                    with ui.row().classes('items-center gap-2 mb-2'):
                        ui.icon('play_circle', color='green')
                        ui.label('Running').classes('text-green-600 font-bold')
                else:
                    with ui.row().classes('items-center gap-2 mb-2'):
                        ui.icon('stop_circle', color='gray')
                        ui.label('Stopped').classes('text-gray-500')
                
                ui.separator().classes('my-2')
                
                # Performance metrics
                ui.label('Performance:').classes('text-sm font-bold mb-1')
                ui.label(
                    f'Target: {stats["target_fps"]:.1f} FPS'
                ).classes('text-sm')
                
                # Color code actual FPS based on target
                actual_fps = stats['actual_fps']
                target_fps = stats['target_fps']
                fps_ratio = actual_fps / target_fps if target_fps > 0 else 0
                
                if fps_ratio >= 0.9:
                    fps_color = 'text-green-600'
                elif fps_ratio >= 0.7:
                    fps_color = 'text-yellow-600'
                else:
                    fps_color = 'text-red-600'
                
                ui.label(
                    f'Actual: {actual_fps:.1f} FPS'
                ).classes(f'text-sm {fps_color}')
                
                ui.label(
                    f'Frames: {stats["frame_count"]:,}'
                ).classes('text-sm')
                
                # New: show dropped frames and pending ticks
                if stats['dropped_frames'] > 0:
                    ui.label(
                        f'Dropped: {stats["dropped_frames"]:,}'
                    ).classes('text-sm text-orange-600')
                
                ui.label(
                    f'Pending: {stats["pending_ticks"]}'
                ).classes('text-sm')
                
            else:
                ui.label('Not initialized').classes('text-gray-500')
            
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
    
    def cleanup(self):
        """
        Manual cleanup method - call this if not using NiceGUI's lifecycle.
        
        This is a fallback for cases where on_app_shutdown isn't called.
        """
        self.on_app_shutdown()

    def run(self):
        """Run the application."""
        print("Starting Enhanced Test App with Canvas Manager...")
        self.create_ui()
        
        try:
            ui.run(
                port=8082,
                show=True, 
                title="Enhanced Haywire Test with Canvas Manager", 
                reload=False
            )
        except KeyboardInterrupt:
            print("\n⚠️ Keyboard interrupt received")
        finally:
            # Ensure cleanup runs even if ui.run exits unexpectedly
            if not self._is_shutting_down:
                self.cleanup()
                
def run_app():
    """Launch the Haywire application."""
    logging.getLogger('haywire.ui.editor.graph_canvas_manager').setLevel(logging.DEBUG)

    app_instance = HaywireApp()

    app.on_shutdown(app_instance.cleanup)

    app_instance.run()


def main():
    """Main entry point — routes CLI subcommands."""
    import argparse

    parser = argparse.ArgumentParser(
        prog='haywire',
        description='Haywire visual programming system',
    )
    subparsers = parser.add_subparsers(dest='command')

    # haywire init <project-name>
    init_parser = subparsers.add_parser(
        'init',
        help='Create a new haywire project',
    )
    init_parser.add_argument('name', help='Project name')
    init_parser.add_argument(
        '--no-sync',
        action='store_true',
        help='Skip running uv sync after scaffolding',
    )
    init_parser.add_argument(
        '--dev',
        action='store_true',
        help='Use editable local sources from this dev repo instead of PyPI',
    )

    # haywire share <library-path>
    share_parser = subparsers.add_parser(
        'share',
        help='Generate a marketplace.toml snippet for sharing a library',
    )
    share_parser.add_argument(
        'library_path',
        nargs='?',
        default=None,
        help='Path to the library directory (e.g. libs/haybale-myproject). '
             'Auto-detected if libs/ contains exactly one library.',
    )

    args = parser.parse_args()

    if args.command == 'init':
        from .init import init_project, _get_dev_repo_root
        dev_repo = _get_dev_repo_root() if args.dev else None
        init_project(args.name, auto_sync=not args.no_sync, dev_repo=dev_repo)
    elif args.command == 'share':
        from .share import share_library
        share_library(args.library_path)
    else:
        # No subcommand = launch the app
        run_app()


if __name__ in {"__main__", "__mp_main__"}:
    main()
