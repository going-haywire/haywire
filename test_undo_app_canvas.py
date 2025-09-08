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
        
        # Initialize library system service
        self.setup_library_system()
        
        # Get services from the library system
        self.setup_services()
        
        # UI state
        self.selected_nodes: set[str] = set()
        self.creation_mode = None  # Stores the node type to create on canvas click
        
        # Statistics
        self.stats = {
            'nodes_created': 0,
            'edges_created': 0,
            'undo_operations': 0,
            'redo_operations': 0
        }
        
        # UI components (will be set during setup)
        self.zoom_container = None
        self.canvas_manager = None
        self.info_panel = None
        self.history_panel = None
        self.stats_container = None
        self.info_container = None 
        self.history_container = None
    
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
        # Get services through DI
        self.node_registry = self.library_service.get_node_registry()
        self.node_factory = self.library_service.get_node_factory()
        self.node_render_factory = self.library_service.get_node_render_factory()
        
        # Get history manager for undo/redo
        self.history_manager = self.library_service.get_history_manager()
        print(f"History manager available: {self.history_manager is not None}")
        
        # Create graph
        self.graph = HaywireGraph("test_graph", "Enhanced Test Graph")
        self.node_factory.add_hot_reload_listener(self.on_hot_reload)
        
        print("Services configured successfully.")
    
    def get_available_nodes(self):
        """Get available node types from the registry."""
        available_nodes = self.node_registry.list_names()
        print(f"Available nodes from registry: {available_nodes}")
        return available_nodes
    
    def create_ui(self):
        """Create the main UI."""
        @ui.page('/', title="Enhanced Haywire Test App with Canvas Manager")
        def main_page():
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
                    ui.label('Enhanced Haywire Test App').classes('text-xl font-bold')
                    
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
                with ui.column() as self.canvas_status_container:
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
                        ui.button(
                            f'Create {node_type}', 
                            on_click=lambda node_type=node_type: self.set_creation_mode(node_type),
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
                with ui.column() as self.stats_container:
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
            ui.label('Node Editor with Canvas Manager').classes('text-lg font-bold mb-2')
            
            # Create the zoom/pan container
            self.zoom_container = ZoomPanContainer(
                min_zoom=0.1,
                max_zoom=3.0,
                initial_zoom=1.0,
                on_zoom_change=self.on_zoom_change,
                on_pan_change=self.on_pan_change
            ).classes('w-full flex-grow border-2 border-gray-300').style('height: calc(100% - 60px);')
            
            # Initialize canvas manager
            self.canvas_manager = GraphCanvasManager(
                graph=self.graph,
                node_render_factory=self.node_render_factory,
                zoom_container=self.zoom_container,
                on_node_position_changed=self.on_node_moved,
                on_connection_created=self.on_connection_created,
                on_connection_removed=self.on_connection_removed,
                on_node_selected=self.on_node_selected
            )
            
            # Register canvas manager for callbacks
            register_canvas_manager(self.canvas_manager)
            
            # Setup client-side interactions
            self.canvas_manager.setup_client_side_interactions()
            
            # Add canvas click handler for node creation
            self.canvas_manager.canvas.on('click', self.on_canvas_click)
            
            self.create_zoom_controls()
            
            # Update canvas status
            self.update_canvas_status()
    
    def create_right_panel(self):
        """Create the right information panel."""
        with ui.card().classes('w-80 overflow-auto').style('height: calc(100vh - 120px);'):
            ui.label('Information & History').classes('text-lg font-bold mb-4')
            
            # Graph Information
            with ui.expansion('Graph Info', icon='info').classes('w-full'):
                with ui.column() as self.info_container:
                    self.update_info_display()
            
            # History Information
            with ui.expansion('Undo/Redo History', icon='history').classes('w-full'):
                with ui.column() as self.history_container:
                    self.update_history_display()
            
            # Selected Nodes
            with ui.expansion('Selection', icon='check_circle').classes('w-full'):
                with ui.column() as self.selection_container:
                    ui.label('No nodes selected').classes('text-gray-500')
    
    def create_zoom_controls(self):
        """Create zoom and pan controls."""
        with ui.row().classes('gap-2 mt-2'):
            ui.button('Fit to View', on_click=lambda: self.zoom_container.zoom_to_fit(), icon='fit_screen').props('outline')
            ui.button('Reset Zoom', on_click=lambda: self.zoom_container.reset_zoom(), icon='center_focus_strong').props('outline')
            ui.button('Zoom In', on_click=lambda: self.zoom_container.zoom_in(), icon='zoom_in').props('outline')
            ui.button('Zoom Out', on_click=lambda: self.zoom_container.zoom_out(), icon='zoom_out').props('outline')
    
    # Event Handlers
    def on_zoom_change(self, zoom_level):
        """Handle zoom change events."""
        if hasattr(self, 'canvas_status_container'):
            self.update_canvas_status()
    
    def on_pan_change(self, pan_x, pan_y):
        """Handle pan change events."""
        if hasattr(self, 'canvas_status_container'):
            self.update_canvas_status()
    
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
            # Create node using factory
            node = self.node_factory.create_instance(
                node_type,
                self.graph,
                position=(click_x, click_y)
            )
            
            # Set position attributes
            node.ui_posX = click_x
            node.ui_posY = click_y
            
            # Use undo system
            if self.history_manager:
                action = AddNodeAction(self.graph, node)
                self.history_manager.add_action(action)
            else:
                self.graph.add_node(node)
            
            # Add visual representation through canvas manager
            if self.canvas_manager.add_node_visual(node, (click_x, click_y)):
                self.stats['nodes_created'] += 1
                self.update_displays()
                ui.notify(f"Created {node.__class__.__name__} at ({click_x}, {click_y})")
            else:
                ui.notify(f"Failed to create visual for {node.__class__.__name__}", type='negative')
                
        except Exception as e:
            ui.notify(f"Error creating node: {str(e)}", type='negative')
            print(f"Error creating node: {e}")
    
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
            
            self.stats['edges_created'] += 1
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
                    action = MoveNodeAction(self.graph, node_id, old_position, new_position)
                    self.history_manager.add_action(action)
                
                # Update node position
                node.ui_posX, node.ui_posY = new_position
                
        except Exception as e:
            print(f"Error handling node move: {e}")
    
    def on_node_selected(self, node_id: str, selected: bool):
        """Handle node selection changes."""
        if selected:
            self.selected_nodes.add(node_id)
        else:
            self.selected_nodes.discard(node_id)
        
        print(f"Node {node_id} {'selected' if selected else 'deselected'}")
        # Update selection display
        self.update_selection_display()
    
    def on_hot_reload(self, registry_key: str, affected_node_ids: List[str]):
        """Handle hot reload notifications."""
        print(f"Hot reload detected for {registry_key}, affecting nodes: {affected_node_ids}")
        ui.notify(f"Hot reload: {registry_key} ({len(affected_node_ids)} nodes)", type='info')
    
    # Action Methods
    def set_creation_mode(self, node_type: str):
        """Set node creation mode."""
        self.creation_mode = node_type
        print(f"Setting creation mode to: {node_type}")
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
            
            self.stats['undo_operations'] += 1
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
            
            self.stats['redo_operations'] += 1
            self.sync_ui_with_graph(nodes_before, nodes_after)
            ui.notify("Redo performed")
        else:
            ui.notify("Nothing to redo")
    
    def sync_ui_with_graph(self, nodes_before: set, nodes_after: set):
        """Synchronize UI with graph changes."""
        self.canvas_manager.sync_with_graph()
        self.update_displays()
    
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
        """Update canvas manager status display."""
        if hasattr(self, 'canvas_status_container'):
            self.canvas_status_container.clear()
            with self.canvas_status_container:
                ui.label(f'✓ Canvas Manager Active').classes('text-green-600 text-sm')
                ui.label(f'Visual Nodes: {len(self.canvas_manager.node_panels)}').classes('text-sm')
                ui.label(f'Visual Connections: {len(self.canvas_manager.connection_paths)}').classes('text-sm')
                if self.zoom_container:
                    ui.label(f'Zoom: {self.zoom_container.current_zoom:.2f}x').classes('text-sm')
                    ui.label(f'Pan: ({self.zoom_container.pan_x:.0f}, {self.zoom_container.pan_y:.0f})').classes('text-sm')
    
    def update_stats_display(self):
        """Update the statistics display."""
        if hasattr(self, 'stats_container'):
            self.stats_container.clear()
            with self.stats_container:
                ui.label(f'Nodes Created: {self.stats["nodes_created"]}')
                ui.label(f'Connections Created: {self.stats["edges_created"]}')
                ui.label(f'Undo Operations: {self.stats["undo_operations"]}')
                ui.label(f'Redo Operations: {self.stats["redo_operations"]}')
    
    def update_info_display(self):
        """Update the information display."""
        if hasattr(self, 'info_container'):
            self.info_container.clear()
            with self.info_container:
                ui.label(f'Graph ID: {self.graph.graph_id}').classes('text-sm')
                ui.label(f'Nodes: {len(self.graph.nodes)}')
                ui.label(f'Connections: {len(self.graph.edges)}')
                
                if self.history_manager:
                    ui.label(f'Can Undo: {self.history_manager.can_undo()}')
                    ui.label(f'Can Redo: {self.history_manager.can_redo()}')
    
    def update_history_display(self):
        """Update the history display."""
        if hasattr(self, 'history_container'):
            self.history_container.clear()
            with self.history_container:
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
        """Update selection display."""
        if hasattr(self, 'selection_container'):
            self.selection_container.clear()
            with self.selection_container:
                if self.selected_nodes:
                    ui.label(f'Selected: {len(self.selected_nodes)} nodes').classes('font-bold')
                    for node_id in list(self.selected_nodes)[:5]:  # Show first 5
                        ui.label(f'• {node_id}').classes('text-xs pl-2')
                    if len(self.selected_nodes) > 5:
                        ui.label(f'... and {len(self.selected_nodes) - 5} more').classes('text-xs pl-2 text-gray-500')
                else:
                    ui.label('No nodes selected').classes('text-gray-500')
    
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
