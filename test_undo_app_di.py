"""
DI-based comprehensive test application for Haywire undo/redo system with pan/zoom integration.

This application demonstrates:
1. Dependency injection for clean service management
2. Registry-based node system with real nodes
3. Pan/zoom functionality with node editor
4. Undo/redo system for graph operations
5. Node factory integration
6. Interactive node creation and manipulation
7. Visual feedback for undo operations

Key improvements with DI and Registry:
- Uses real nodes from the registry system
- Clean separation of configuration and business logic
- Easy testing and mocking
- Flexible service management
- No manual wiring of dependencies
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


class UndoRedoTestAppDI:
    """DI-based main application class for testing undo/redo functionality."""
    
    def __init__(self):
        print("Setting up DI system with undo/redo support...")
        
        # Initialize library system service (like registry demo)
        self.setup_library_system()
        
        # Get services from the library system
        self.setup_services()
        
        # UI state
        self.selected_nodes: set[str] = set()
        self.drag_state = None
        self.connection_mode = False
        self.connection_start = None
        
        # Node creation state
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
        self.info_panel = None
        self.history_panel = None
        self.node_panels = {}
    
    def setup_library_system(self):
        """Initialize the library system service (like registry demo)."""
        # Store undo config for UI access
        self.undo_config = DEVELOPMENT_CONFIG
        
        # Create and initialize the library system service with undo support
        self.library_service = create_library_system_service(
            project_root=project_root,
            enable_file_watching=True,
            undo_config=self.undo_config
        )
        
        print("DI system initialized successfully.")
        
        # Print registry status to see what nodes are available
        self.library_service.print_registry_status()
    
    def setup_services(self):
        """Get all required services from the library system."""
        print("Services configured successfully.")
        
        # Get services through DI (like registry demo)
        self.node_registry = self.library_service.get_node_registry()
        self.node_factory = self.library_service.get_node_factory()
        self.node_render_factory = self.library_service.get_node_render_factory()
        
        # Get history manager for undo/redo
        self.history_manager = self.library_service.get_history_manager()
        print(f"History manager available: {self.history_manager is not None}")
        
        # Create graph
        self.graph = HaywireGraph("test_graph", "Test Graph")
        self.node_factory.add_hot_reload_listener(self.on_hot_reload)
        
        print("Services configured successfully.")
        print(f"History manager available: {self.history_manager is not None}")
    
    def get_available_nodes(self):
        """Get available node types from the registry."""
        # Get node names from the registry (this will show what's actually available)
        available_nodes = self.node_registry.list_names()
        print(f"Available nodes from registry: {available_nodes}")
        return available_nodes
    
    def create_ui(self):
        """Create the main UI."""
        @ui.page('/')
        def main_page():
            # Add CSS to fix text input interactions within zoom container
            ui.add_head_html('''
            <style>
            /* Ensure text inputs and interactive elements work within zoom container */
            .zoom-debug-node input,
            .zoom-debug-node textarea, 
            .zoom-debug-node select,
            .zoom-debug-node button {
                pointer-events: auto !important;
                user-select: auto !important;
                -webkit-user-select: auto !important;
                -moz-user-select: auto !important;
                -ms-user-select: auto !important;
            }
            
            /* Prevent zoom container from interfering with input focus */
            .zoom-debug-node input:focus,
            .zoom-debug-node textarea:focus {
                z-index: 10000 !important;
                position: relative !important;
            }
            
            /* Ensure node containers don't block mouse events */
            .zoom-debug-node {
                pointer-events: auto !important;
            }
            
            /* CRITICAL FIX: Disable hover scaling for node cards */
            .zoom-debug-node.haywire-zoomable-lod0:hover {
                transform: none !important;
                box-shadow: none !important;
            }
            
            /* Instead, provide subtle hover feedback for nodes */
            .zoom-debug-node:hover .node-card {
                box-shadow: 0 4px 12px rgba(0,0,0,0.15) !important;
                transition: box-shadow 0.2s ease !important;
            }
            </style>
            ''')
            
            # Create the main page layout
            self.create_header()
            
            with ui.row().classes('w-full gap-4').style('height: calc(100vh - 80px);'):
                self.create_left_panel()
                self.create_main_editor()
                self.create_right_panel()
    
    def create_header(self):
        """Create the application header with main controls."""
        with ui.header().classes('bg-blue-600 text-white px-4 py-2'):
            with ui.row().classes('w-full justify-between items-center'):
                ui.label('DI-based Haywire Undo/Redo Test Application').classes('text-xl font-bold')
                
                with ui.row().classes('gap-2'):
                    # Undo/Redo controls
                    self.undo_button = ui.button('↶ Undo', on_click=self.undo_action)
                    self.redo_button = ui.button('↷ Redo', on_click=self.redo_action)
                    
                    ui.separator().props('vertical color=white')
                    
                    # Graph controls
                    ui.button('Clear Graph', on_click=self.clear_graph).props('color=red')
                    ui.button('Random Graph', on_click=self.create_random_graph).props('color=green')
                    
                    ui.separator().props('vertical color=white')
                    
                    # DI info
                    ui.label(f'DI: ✓ History: {"✓" if self.history_manager else "✗"}').classes('text-sm')
    
    def create_left_panel(self):
        """Create the left control panel."""
        with ui.card().classes('w-80 overflow-auto').style('height: calc(100vh - 120px);'):
            ui.label('Controls & Tools').classes('text-lg font-bold mb-4')
            
            # DI Status
            with ui.expansion('DI System Status', icon='settings').classes('w-full'):
                di_status = ui.column().classes('gap-1')
                with di_status:
                    ui.label(f'✓ Node Registry: {len(self.node_registry.list_names())} nodes')
                    ui.label(f'{"✓" if self.history_manager else "✗"} History Manager: {"Available" if self.history_manager else "Not Available"}')
                    ui.label(f'✓ Node Factory: Ready')
                    ui.label(f'✓ Graph: {len(self.graph.nodes)} nodes, {len(self.graph.edges)} edges')
            
            # Node creation tools
            with ui.expansion('Node Creation', icon='add_circle').classes('w-full'):
                ui.label('Click to create nodes:').classes('mb-2')
                
                with ui.column().classes('gap-2'):
                    # Get available nodes from registry
                    available_nodes = self.get_available_nodes()
                    
                    # Create buttons for available nodes
                    if available_nodes:
                        for i, node_key in enumerate(available_nodes[:5]):  # Limit to first 5 for UI
                            # Create a simple display name from the registry key
                            display_name = node_key.split(':')[-1] if ':' in node_key else node_key
                            button_text = f'🔧 {display_name}'
                            ui.button(button_text, 
                                     on_click=lambda nk=node_key: self.set_creation_mode(nk)).classes('w-full')
                    else:
                        ui.label('No nodes available in registry').classes('text-red-500')
            
            # Tools
            with ui.expansion('Tools', icon='build').classes('w-full'):
                with ui.column().classes('gap-2'):
                    self.selection_mode_button = ui.button('🔍 Selection Mode', 
                                                         on_click=self.toggle_selection_mode).classes('w-full')
                    self.connection_mode_button = ui.button('🔗 Connection Mode', 
                                                           on_click=self.toggle_connection_mode).classes('w-full')
                    ui.button('🗑️ Delete Selected', 
                             on_click=self.delete_selected).classes('w-full')
            
            # Statistics
            with ui.expansion('Statistics', icon='analytics').classes('w-full'):
                self.stats_container = ui.column().classes('gap-1')
                self.update_stats_display()
            
            # Configuration
            with ui.expansion('Configuration', icon='settings').classes('w-full'):
                with ui.column().classes('gap-2'):
                    ui.label('Undo Settings:').classes('font-bold')
                    
                    if self.history_manager:
                        self.auto_grouping_switch = ui.switch('Auto-grouping', 
                                                            value=self.undo_config.enable_auto_grouping,
                                                            on_change=self.toggle_auto_grouping)
                        
                        self.action_merging_switch = ui.switch('Action merging', 
                                                             value=self.undo_config.enable_action_merging,
                                                             on_change=self.toggle_action_merging)
                        
                        ui.slider(min=10, max=200, value=self.undo_config.max_actions, 
                                 on_change=lambda e: self.set_max_actions(e.value)).props('label="Max Actions"')
                    else:
                        ui.label('History manager not available').classes('text-red-500')
    
    def create_main_editor(self):
        """Create the main node editor with pan/zoom."""
        with ui.card().classes('flex-grow').style('min-width: 600px; height: calc(100vh - 120px);'):
            ui.label('Node Editor (DI-powered)').classes('text-lg font-bold mb-2')
            
            # Create the zoom/pan container
            self.zoom_container = ZoomPanContainer(
                min_zoom=0.1,
                max_zoom=3.0,
                initial_zoom=1.0,
                on_zoom_change=self.on_zoom_change,
                on_pan_change=self.on_pan_change
            ).classes('w-full flex-grow border-2 border-gray-300').style('height: calc(100% - 60px);')
            
            # Setup container event handlers
            self.zoom_container.on('click', self.on_canvas_click)
            self.zoom_container.on('dragstart', self.on_drag_start)
            self.zoom_container.on('drag', self.on_drag)
            self.zoom_container.on('dragend', self.on_drag_end)
            
            # Add content to the container - use content_container instead of custom div
            with self.zoom_container.content_container:
                # Create a large canvas area with proper styling and debug border
                self.canvas = ui.element('div').classes('relative').style(
                    'width: 4000px; height: 4000px; '
                    'background: linear-gradient(90deg, #f0f0f0 1px, transparent 1px), '
                    'linear-gradient(180deg, #f0f0f0 1px, transparent 1px); '
                    'background-size: 50px 50px; '
                    'border: 3px solid green; '  # Green border to distinguish from original
                    'position: relative; '
                    'overflow: visible;'
                )
                
                # Add a test element to verify canvas is working
                with self.canvas:
                    with ui.card().classes('absolute').style(
                        'left: 100px; top: 100px; width: 200px; height: 100px; '
                        'background-color: green; z-index: 100; border: 2px solid black;'
                    ):
                        ui.label('DI TEST NODE - Canvas is working!').classes('text-white font-bold')
            
            # Add zoom controls
            self.create_zoom_controls()
    
    def create_right_panel(self):
        """Create the right information panel."""
        with ui.card().classes('w-80 overflow-auto').style('height: calc(100vh - 120px);'):
            ui.label('Information & History').classes('text-lg font-bold mb-4')
            
            # Current state info
            with ui.expansion('Current State', icon='info').classes('w-full'):
                self.info_container = ui.column().classes('gap-1')
                self.update_info_display()
            
            # Undo history
            with ui.expansion('Undo History', icon='history').classes('w-full'):
                self.history_container = ui.column().classes('gap-1 max-h-60 overflow-auto')
                self.update_history_display()
            
            # DI Architecture info
            with ui.expansion('DI Architecture', icon='architecture').classes('w-full'):
                ui.html('''
                <div class="p-2">
                    <h4 class="font-bold mb-2">Benefits:</h4>
                    <ul class="list-disc ml-4 mb-3">
                        <li>Clean service separation</li>
                        <li>Easy testing and mocking</li>
                        <li>Flexible configuration</li>
                        <li>No manual wiring</li>
                    </ul>
                    <h4 class="font-bold mb-2">Services:</h4>
                    <ul class="list-disc ml-4">
                        <li>NodeRegistry (singleton)</li>
                        <li>HistoryManager (singleton)</li>
                        <li>NodeFactory (singleton)</li>
                        <li>Graph (app-managed)</li>
                    </ul>
                </div>
                ''')
    
    def create_zoom_controls(self):
        """Create zoom and pan controls."""
        with ui.row().classes('gap-2 mt-2'):
            ui.button('🔍➕', on_click=lambda: self.zoom_container.zoom_in()).classes('w-10 h-10')
            ui.button('🔍➖', on_click=lambda: self.zoom_container.zoom_out()).classes('w-10 h-10')
            ui.button('🎯', on_click=lambda: self.zoom_container.reset_view()).classes('w-10 h-10')
            ui.button('📐', on_click=lambda: self.zoom_container.fit_to_content()).classes('w-10 h-10')
    
    # Event Handlers
    def on_zoom_change(self, zoom_level):
        """Handle zoom change events."""
        pass
    
    def on_pan_change(self, pan_x, pan_y):
        """Handle pan change events."""
        pass
    
    def on_canvas_click(self, event):
        """Handle canvas click events."""
        print(f"Canvas clicked at: {event}")
        
        # If we're in creation mode, create a node at the clicked position
        if self.creation_mode:
            try:
                # Extract position from the event
                # The event args contain offsetX and offsetY which are relative to the canvas
                click_x = event.args.get('offsetX', 0)
                click_y = event.args.get('offsetY', 0)
                
                print(f"Creating {self.creation_mode} at position ({click_x}, {click_y})")
                
                # Create the node using the factory (pure utility)
                node = self.node_factory.create_instance(
                    self.creation_mode,
                    self.graph,
                    position=(click_x, click_y)
                )
                
                # Use the clean architecture: Create AddNodeAction for undo support
                if self.history_manager:
                    # Use undo system - action will handle adding to graph
                    action = AddNodeAction(self.graph, node)
                    self.history_manager.add_action(action)
                else:
                    # No undo system - add directly to graph
                    self.graph.add_node(node)
                
                self.stats['nodes_created'] += 1
                
                # Create a visual representation on the canvas
                self.create_node_visual(node, click_x, click_y)
                
                # Update displays
                self.update_stats_display()
                self.update_info_display()
                self.update_history_display()
                
                # Get node name safely
                node_name = getattr(node, 'node_label', None) or getattr(node, 'name', None) or node.node_id or node.__class__.__name__
                ui.notify(f"Created {node_name} at ({click_x}, {click_y})")
                
                # Reset creation mode (single-shot creation)
                self.creation_mode = None
                
            except Exception as e:
                print(f"Error creating node: {e}")
                ui.notify(f"Error creating node: {str(e)}", type='negative')
    
    def create_node_visual(self, node, x, y):
        """Create a visual representation of the node using the proper rendering system."""
        try:
            # Create a container for the node at the specified position
            with self.canvas:
                with ui.column().classes('absolute haywire-zoomable-lod0').style(
                    f'left: {x}px; top: {y}px; z-index: 100; '
                    f'pointer-events: auto; user-select: auto;'
                ) as container:
                    # Use the proper UINode and NodeRenderFactory system (like registry demo)
                    ui_node = UINode(node, self.node_render_factory, container)
                    ui_node.render()  # This uses the registry's renderer system
                    
                    # Store reference to the UI node and container
                    self.node_panels[node.node_id] = {
                        'ui_node': ui_node,
                        'container': container,
                        'position': (x, y)
                    }
                    
                    print(f"Created visual for node {node.node_id} using NodeRenderFactory")
                    print(f"Node inlets: {list(node.inlets.keys()) if hasattr(node, 'inlets') else 'No inlets'}")
                    print(f"Current canvas zoom: {getattr(self.canvas, 'current_zoom', 'unknown')}")
                    
                    # Debug: Print widget instances that were created
                    if ui_node.current_ui_card:
                        widget_instances = ui_node.current_ui_card.widget_instances
                        print(f"Widget instances created: {list(widget_instances.keys())}")
                        for widget_id, widget in widget_instances.items():
                            print(f"  {widget_id}: {widget.__class__.__name__} -> {widget.get_value() if hasattr(widget, 'get_value') else 'No value'}")
                    
                    # Add debugging for pointer events - check if node elements have correct CSS
                    container.classes('zoom-debug-node')
                    
        except Exception as e:
            print(f"Error creating node visual with NodeRenderFactory: {e}")
            import traceback
            traceback.print_exc()
            # Fallback to basic rendering if render factory fails
            self._create_basic_node_visual(node, x, y)
    
    def _create_basic_node_visual(self, node, x, y):
        """Fallback method for basic node visualization."""
        with self.canvas:
            # Create a basic visual node element as fallback
            node_id = f"visual_{node.node_id}"
            node_color = getattr(node, 'ui_color', '#4A90E2')
            
            with ui.card().classes('absolute cursor-pointer').style(
                f'left: {x}px; top: {y}px; width: 150px; min-height: 80px; '
                f'background-color: {node_color}; z-index: 100; '
                f'border: 2px solid #333; border-radius: 8px;'
            ) as card:
                card.props(f'id="{node_id}"')
                
                with ui.column().classes('p-2 gap-1'):
                    # Get node display name safely
                    node_name = getattr(node, 'node_label', None) or getattr(node, 'name', None) or node.node_id or node.__class__.__name__
                    node_desc = getattr(node, 'node_description', None) or getattr(node, 'description', 'Node')
                    
                    ui.label(node_name).classes('text-white font-bold text-sm')
                    ui.label(node_desc).classes('text-white text-xs opacity-80')
                    ui.label(f'ID: {node.node_id}').classes('text-white text-xs opacity-60')
            
            # Store reference to visual element
            self.node_panels[node.node_id] = {
                'container': card,
                'position': (x, y)
            }
            print(f"Created basic visual for node {node.node_id} (fallback)")
    
    def remove_node_visual(self, node_id):
        """Remove a node's visual representation."""
        if node_id in self.node_panels:
            visual_data = self.node_panels[node_id]
            
            # Handle both UINode and basic rendering systems
            if 'ui_node' in visual_data:
                # UINode-based rendering
                ui_node = visual_data['ui_node']
                container = visual_data['container']
                # Clean up UINode properly
                if hasattr(ui_node, 'cleanup'):
                    ui_node.cleanup()
                container.delete()
                print(f"Removed UINode visual for {node_id}")
            elif 'container' in visual_data:
                # Basic rendering
                visual_data['container'].delete()
                print(f"Removed basic visual for {node_id}")
            
            del self.node_panels[node_id]
        else:
            print(f"No visual found for node {node_id}")
    
    def on_drag_start(self, event):
        """Handle drag start events."""
        print(f"Drag started: {event}")
    
    def on_drag(self, event):
        """Handle drag events."""
        pass
    
    def on_drag_end(self, event):
        """Handle drag end events."""
        print(f"Drag ended: {event}")
    
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
    
    def toggle_connection_mode(self):
        """Toggle connection mode."""
        self.connection_mode = not self.connection_mode
        print(f"Connection mode: {self.connection_mode}")
        ui.notify(f"Connection mode: {'ON' if self.connection_mode else 'OFF'}")
    
    def delete_selected(self):
        """Delete selected nodes."""
        if self.selected_nodes:
            print(f"Deleting {len(self.selected_nodes)} selected nodes")
            ui.notify(f"Deleted {len(self.selected_nodes)} nodes")
            self.selected_nodes.clear()
        else:
            ui.notify("No nodes selected")
    
    def undo_action(self):
        """Perform undo operation."""
        if self.history_manager and self.history_manager.can_undo():
            # Store current state before undo
            nodes_before = set(self.graph.nodes.keys())
            
            # Perform the undo
            self.history_manager.undo()
            
            # Update UI based on changes
            nodes_after = set(self.graph.nodes.keys())
            self.sync_ui_with_graph(nodes_before, nodes_after)
            
            self.stats['undo_operations'] += 1
            self.update_stats_display()
            self.update_history_display()
            ui.notify("Undo performed")
        else:
            ui.notify("Cannot undo" + ("" if self.history_manager else " (no history manager)"))
    
    def redo_action(self):
        """Perform redo operation."""
        if self.history_manager and self.history_manager.can_redo():
            # Store current state before redo
            nodes_before = set(self.graph.nodes.keys())
            
            # Perform the redo
            self.history_manager.redo()
            
            # Update UI based on changes
            nodes_after = set(self.graph.nodes.keys())
            self.sync_ui_with_graph(nodes_before, nodes_after)
            
            self.stats['redo_operations'] += 1
            self.update_stats_display()
            self.update_history_display()
            ui.notify("Redo performed")
        else:
            ui.notify("Cannot redo" + ("" if self.history_manager else " (no history manager)"))
    
    def sync_ui_with_graph(self, nodes_before: set, nodes_after: set):
        """Synchronize UI visual representations with the current graph state."""
        # Find nodes that were removed
        removed_nodes = nodes_before - nodes_after
        for node_id in removed_nodes:
            if node_id in self.node_panels:
                print(f"Removing visual for node {node_id}")
                self.remove_node_visual(node_id)
        
        # Find nodes that were added
        added_nodes = nodes_after - nodes_before
        for node_id in added_nodes:
            if node_id in self.graph.nodes and node_id not in self.node_panels:
                node = self.graph.nodes[node_id]
                print(f"Creating visual for node {node_id}")
                # Recreate visual representation
                x = getattr(node, 'ui_posX', 100)
                y = getattr(node, 'ui_posY', 100)
                self.create_node_visual(node, x, y)
        
        # Update info display
        self.update_info_display()
    
    def clear_graph(self):
        """Clear the entire graph."""
        if self.history_manager:
            # Use undo-enabled clearing with proper actions
            node_ids = list(self.graph.nodes.keys())
            for node_id in node_ids:
                # Create RemoveNodeAction for undo/redo support
                node = self.graph.nodes.get(node_id)
                if node:
                    action = RemoveNodeAction(self.graph, node_id, node)
                    self.history_manager.execute(action)
                    # Remove visual representation
                    self.remove_node_visual(node_id)
                    print(f"Removed node {node_id} with undo support")
        else:
            # Direct clearing
            self.graph.clear()
            # Clear visual representations
            for node_id in list(self.node_panels.keys()):
                self.remove_node_visual(node_id)
            self.node_panels.clear()
        
        self.update_stats_display()
        self.update_info_display()
        self.update_history_display()
        ui.notify("Graph cleared")
    
    def create_random_graph(self):
        """Create a random graph for testing."""
        # Get available node types from registry
        available_nodes = self.get_available_nodes()
        if not available_nodes:
            ui.notify("No nodes available in registry", type='warning')
            return
            
        # Create a few random nodes
        for i in range(random.randint(3, 6)):
            node_type = random.choice(available_nodes)
            pos = (random.randint(200, 800), random.randint(200, 800))
            
            try:
                # Use node factory to create nodes (pure utility)
                node = self.node_factory.create_instance(
                    node_type, 
                    self.graph, 
                    position=pos
                )
                
                # Add node to graph (temporary - should be handled by actions)
                self.graph.add_node(node)
                
                # Create visual representation
                self.create_node_visual(node, pos[0], pos[1])
                
                self.stats['nodes_created'] += 1
            except Exception as e:
                print(f"Error creating node {node_type}: {e}")
        
        self.update_stats_display()
        self.update_info_display()
        self.update_history_display()
        ui.notify(f"Random graph created!")
    
    # Configuration Methods
    def toggle_auto_grouping(self, enabled: bool):
        """Toggle auto-grouping setting."""
        if self.history_manager:
            self.undo_config.enable_auto_grouping = enabled
            print(f"Auto-grouping: {enabled}")
    
    def toggle_action_merging(self, enabled: bool):
        """Toggle action merging setting."""
        if self.history_manager:
            self.undo_config.enable_action_merging = enabled
            print(f"Action merging: {enabled}")
    
    def set_max_actions(self, max_actions: int):
        """Set maximum number of undo actions."""
        if self.history_manager:
            self.undo_config.max_actions = max_actions
            print(f"Max actions: {max_actions}")
    
    # UI Update Methods
    def update_stats_display(self):
        """Update the statistics display."""
        if hasattr(self, 'stats_container'):
            self.stats_container.clear()
            with self.stats_container:
                ui.label(f'Nodes: {len(self.graph.nodes)}')
                ui.label(f'Edges: {len(self.graph.edges)}')
                ui.label(f'Created: {self.stats["nodes_created"]}')
                ui.label(f'Undo Ops: {self.stats["undo_operations"]}')
                ui.label(f'Redo Ops: {self.stats["redo_operations"]}')
                if self.history_manager:
                    stats = self.history_manager.get_history_stats()
                    ui.label(f'History: {stats["action_count"]} actions')
    
    def update_info_display(self):
        """Update the information display."""
        if hasattr(self, 'info_container'):
            self.info_container.clear()
            with self.info_container:
                ui.label(f'Graph: {self.graph.name}')
                ui.label(f'Nodes: {len(self.graph.nodes)}')
                ui.label(f'Edges: {len(self.graph.edges)}')
                ui.label(f'Selected: {len(self.selected_nodes)}')
                if self.history_manager:
                    ui.label(f'Can Undo: {"Yes" if self.history_manager.can_undo() else "No"}')
                    ui.label(f'Can Redo: {"Yes" if self.history_manager.can_redo() else "No"}')
                else:
                    ui.label('History: Not Available')
    
    def update_history_display(self):
        """Update the history display."""
        if hasattr(self, 'history_container'):
            self.history_container.clear()
            with self.history_container:
                if self.history_manager:
                    # Show current state
                    stats = self.history_manager.get_history_stats()
                    ui.label(f'History Items: {stats["total_items"]}').classes('font-bold')
                    ui.label(f'Actions: {stats["action_count"]}').classes('font-bold')
                    ui.label(f'Current Index: {stats["current_index"]}').classes('text-sm')
                    
                    # Show what can be undone/redone
                    undo_desc = self.history_manager.get_undo_description()
                    if undo_desc:
                        ui.label(f'Next Undo: {undo_desc}').classes('text-sm text-blue-600')
                    
                    redo_desc = self.history_manager.get_redo_description()
                    if redo_desc:
                        ui.label(f'Next Redo: {redo_desc}').classes('text-sm text-green-600')
                        
                    if not undo_desc and not redo_desc:
                        ui.label('No operations available').classes('text-sm text-gray-500')
                else:
                    ui.label('History manager not available').classes('text-red-500')
    
    def run(self):
        """Run the application."""
        print("Starting DI-based Undo/Redo Test App...")
        self.create_ui()
        ui.run(port=8081, show=True, title="DI-based Haywire Undo/Redo Test", reload=False)


def main():
    """Main entry point."""
    app = UndoRedoTestAppDI()
    app.run()


if __name__ in {"__main__", "__mp_main__"}:
    main()
