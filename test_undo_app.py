"""
Comprehensive test application for Haywire undo/redo system with pan/zoom integration.

This application demonstrates:
1. Pan/zoom functionality with node editor
2. Undo/redo system for graph operations
3. Node factory integration
4. Interactive node creation and manipulation
5. Visual feedback for undo operations
"""

from nicegui import ui, events
import time
import random
import json
from typing import Dict, List, Optional, Tuple

# Haywire imports
from haywire.ui.pan_zoom.zoom_pan_vue import ZoomPanContainer
from haywire.core.graph.graph import HaywireGraph, Edge, EdgeType
from haywire.core.node.node import BaseNode
from haywire.core.node.node_factory import NodeFactory
from haywire.core.inventory.registry.node import NodeRegistry
from haywire.undo.history_manager import HistoryManager
from haywire.undo.config import UndoConfig, DEVELOPMENT_CONFIG
from haywire.undo.actions.graph_actions import (
    AddNodeAction, RemoveNodeAction, MoveNodeAction, 
    AddEdgeAction, RemoveEdgeAction, ChangeSelectionAction, SelectionState
)


# Mock Node Classes for Testing
class TestMathNode(BaseNode):
    """A simple math node for testing."""
    
    # Required class attributes
    node_label = "Math Node"
    node_search_tags = ["math", "calculation", "operation"]
    node_menu = "Test/Math"
    
    def __init__(self, node_id: str, graph: HaywireGraph):
        super().__init__(node_id, graph)
        self.name = "Math Node"
        self.description = "Performs mathematical operations"
        self.ui_posX = 0.0
        self.ui_posY = 0.0
        self.ui_color = "#4A90E2"


class TestSourceNode(BaseNode):
    """A source node for testing."""
    
    # Required class attributes
    node_label = "Source Node"
    node_search_tags = ["source", "input", "generator"]
    node_menu = "Test/Source"
    
    def __init__(self, node_id: str, graph: HaywireGraph):
        super().__init__(node_id, graph)
        self.name = "Source Node"
        self.description = "Generates data"
        self.ui_posX = 0.0
        self.ui_posY = 0.0
        self.ui_color = "#7ED321"


class TestSinkNode(BaseNode):
    """A sink node for testing."""
    
    # Required class attributes
    node_label = "Sink Node"
    node_search_tags = ["sink", "output", "consumer"]
    node_menu = "Test/Sink"
    
    def __init__(self, node_id: str, graph: HaywireGraph):
        super().__init__(node_id, graph)
        self.name = "Sink Node"
        self.description = "Consumes data"
        self.ui_posX = 0.0
        self.ui_posY = 0.0
        self.ui_color = "#F5A623"


class UndoRedoTestApp:
    """Main application class for testing undo/redo functionality."""
    
    def __init__(self):
        # Initialize core components
        self.setup_core_components()
        
        # UI state
        self.selected_nodes: set[str] = set()
        self.drag_state = None
        self.connection_mode = False
        self.connection_start = None
        
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
    
    def setup_core_components(self):
        """Initialize the core Haywire components."""
        # Create configuration optimized for development/testing
        self.undo_config = DEVELOPMENT_CONFIG
        
        # Initialize undo system
        self.history_manager = HistoryManager(self.undo_config)
        
        # Create graph
        self.graph = HaywireGraph("test_graph", "Test Graph")
        
        # Setup node registry with test nodes
        self.node_registry = NodeRegistry()
        self._register_test_nodes()
        
        # Create node factory
        self.node_factory = NodeFactory(self.node_registry, self.history_manager)
        
        # Setup hot reload listener for feedback
        self.node_factory.add_hot_reload_listener(self.on_hot_reload)
    
    def _register_test_nodes(self):
        """Register test node classes."""
        # Create mock library metadata for testing
        from haywire.core.inventory.base import LibraryMetadata
        from haywire.core.inventory.utils import reg_key
        
        test_metadata = LibraryMetadata(
            name="test_library",
            version="1.0.0",
            description="Test nodes for undo/redo demonstration",
            author="Test Author",
            url="",
            author_url="",
            help_url=""
        )
        
        # Register each test node properly
        test_nodes = {
            'math_node': TestMathNode,
            'source_node': TestSourceNode,
            'sink_node': TestSinkNode
        }
        
        for key, node_class in test_nodes.items():
            # Generate the correct registry key using the utility function
            registry_key = reg_key(test_metadata.name, node_class.__name__)
            print(f"Registering {node_class.__name__} with key: {registry_key}")
            
            # Register the node with the registry
            self.node_registry.register_node(node_class, test_metadata)
    
    def create_ui(self):
        """Create the main UI."""
        @ui.page('/', title="Haywire Undo/Redo Test App")
        def main_page():
            # Header must be a direct child of the page
            self.create_header()
            
            # Main content area
            with ui.column().classes('w-full bg-gray-50').style('height: calc(100vh - 64px);'):
                with ui.row().classes('w-full gap-4 flex-grow'):
                    self.create_left_panel()
                    self.create_main_editor()
                    self.create_right_panel()
    
    def create_header(self):
        """Create the application header with main controls."""
        with ui.header().classes('bg-blue-600 text-white px-4 py-2'):
            with ui.row().classes('w-full justify-between items-center'):
                ui.label('Haywire Undo/Redo Test Application').classes('text-xl font-bold')
                
                with ui.row().classes('gap-2'):
                    # Undo/Redo controls
                    self.undo_button = ui.button('↶ Undo', on_click=self.undo_action)
                    self.redo_button = ui.button('↷ Redo', on_click=self.redo_action)
                    
                    ui.separator().props('vertical color=white')
                    
                    # Graph controls
                    ui.button('Clear Graph', on_click=self.clear_graph).props('color=red')
                    ui.button('Random Graph', on_click=self.create_random_graph).props('color=green')
    
    def create_left_panel(self):
        """Create the left control panel."""
        with ui.card().classes('w-80 overflow-auto').style('height: calc(100vh - 120px);'):
            ui.label('Controls & Tools').classes('text-lg font-bold mb-4')
            
            # Node creation tools
            with ui.expansion('Node Creation', icon='add_circle').classes('w-full'):
                ui.label('Click to create nodes:').classes('mb-2')
                
                with ui.column().classes('gap-2'):
                    ui.button('➕ Math Node', 
                             on_click=lambda: self.set_creation_mode('test_library:test.math.node')).classes('w-full')
                    ui.button('🔴 Source Node', 
                             on_click=lambda: self.set_creation_mode('test_library:test.source.node')).classes('w-full')
                    ui.button('⚫ Sink Node', 
                             on_click=lambda: self.set_creation_mode('test_library:test.sink.node')).classes('w-full')
            
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
                    
                    self.auto_grouping_switch = ui.switch('Auto-grouping', 
                                                        value=self.undo_config.enable_auto_grouping,
                                                        on_change=self.toggle_auto_grouping)
                    
                    self.action_merging_switch = ui.switch('Action merging', 
                                                         value=self.undo_config.enable_action_merging,
                                                         on_change=self.toggle_action_merging)
                    
                    ui.slider(min=10, max=200, value=self.undo_config.max_actions, 
                             on_change=lambda e: self.set_max_actions(e.value)).props('label="Max Actions"')
    
    def create_main_editor(self):
        """Create the main node editor with pan/zoom."""
        with ui.card().classes('flex-grow').style('min-width: 600px; height: calc(100vh - 120px);'):
            ui.label('Node Editor').classes('text-lg font-bold mb-2')
            
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
                    'border: 3px solid blue; '  # Debug border for canvas
                    'position: relative; '
                    'overflow: visible;'
                )
                
                # Add a test element to verify canvas is working
                with self.canvas:
                    with ui.card().classes('absolute').style(
                        'left: 100px; top: 100px; width: 200px; height: 100px; '
                        'background-color: red; z-index: 100; border: 2px solid black;'
                    ):
                        ui.label('TEST NODE - Canvas is working!').classes('text-white font-bold')
            
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
            
            # Selected nodes info
            with ui.expansion('Selection', icon='radio_button_checked').classes('w-full'):
                self.selection_container = ui.column().classes('gap-1')
                self.update_selection_display()
    
    def create_zoom_controls(self):
        """Create zoom control buttons."""
        with ui.element('div').classes('absolute top-2 right-2 flex gap-1'):
            ui.button('+', on_click=self.zoom_container.zoom_in).props('round dense size=sm')
            ui.button('−', on_click=self.zoom_container.zoom_out).props('round dense size=sm')
            ui.button('⌂', on_click=self.zoom_container.reset_view).props('round dense size=sm')
            ui.button('⛶', on_click=self.zoom_container.fit_to_content).props('round dense size=sm')
    
    # Event Handlers
    
    def on_canvas_click(self, event):
        """Handle clicks on the canvas."""
        if hasattr(self, 'creation_mode') and self.creation_mode:
            # Create node at click position
            x = event.args.get('offsetX', 0)
            y = event.args.get('offsetY', 0)
            self.create_node_at_position(self.creation_mode, x, y)
            self.creation_mode = None
    
    def on_drag_start(self, event):
        """Handle start of drag operation."""
        target_id = event.args.get('target_id')
        if target_id and target_id.startswith('node_'):
            node_id = target_id.replace('node_', '')
            self.drag_state = {
                'node_id': node_id,
                'start_x': event.args.get('x', 0),
                'start_y': event.args.get('y', 0)
            }
    
    def on_drag(self, event):
        """Handle drag operation."""
        if self.drag_state:
            node_id = self.drag_state['node_id']
            x = event.args.get('x', 0)
            y = event.args.get('y', 0)
            self.move_node_to_position(node_id, x, y, use_undo=False)
    
    def on_drag_end(self, event):
        """Handle end of drag operation."""
        if self.drag_state:
            node_id = self.drag_state['node_id']
            final_x = event.args.get('x', 0)
            final_y = event.args.get('y', 0)
            
            # Create undo action for the complete drag operation
            self.node_factory.move_node(self.graph, node_id, final_x, final_y, use_undo=True)
            
            self.drag_state = None
            self.update_all_displays()
    
    def on_zoom_change(self, zoom):
        """Handle zoom level changes."""
        self.update_info_display()
    
    def on_pan_change(self, x, y):
        """Handle pan position changes."""
        self.update_info_display()
    
    def on_hot_reload(self, registry_key: str, affected_node_ids: List[str]):
        """Handle hot reload notifications."""
        ui.notify(f'Hot reload: {registry_key} affected {len(affected_node_ids)} nodes', 
                 type='info', timeout=3000)
    
    # Node Operations
    
    def set_creation_mode(self, node_type: str):
        """Set the node creation mode."""
        self.creation_mode = node_type
        ui.notify(f'Click on canvas to create {node_type}', type='info')
    
    def create_node_at_position(self, node_type: str, x: float, y: float):
        """Create a node at the specified position."""
        try:
            node = self.node_factory.create_node(
                node_type, 
                self.graph, 
                position=(x, y),
                use_undo=True
            )
            
            self.stats['nodes_created'] += 1
            
            # Create UI immediately (synchronously)
            self.create_node_ui(node)
            self.update_all_displays()
            
            ui.notify(f'Created {node.name} at ({x:.0f}, {y:.0f})', type='positive')
            
        except Exception as e:
            ui.notify(f'Failed to create node: {e}', type='negative')
            print(f"Node creation error: {e}")
            import traceback
            traceback.print_exc()
    
    def create_node_ui(self, node: BaseNode):
        """Create UI representation for a node."""
        print(f"Creating UI for node {node.node_id} at ({node.ui_posX}, {node.ui_posY})")
        print(f"Canvas object: {self.canvas}")
        print(f"Canvas classes: {self.canvas.classes if hasattr(self.canvas, 'classes') else 'N/A'}")
        print(f"Zoom container: {self.zoom_container}")
        
        if not hasattr(self, 'canvas') or self.canvas is None:
            print("ERROR: Canvas not available!")
            return
            
        try:
            with self.canvas:
                node_card = ui.card().classes('absolute cursor-pointer select-none').style(
                    f'left: {node.ui_posX}px; top: {node.ui_posY}px; '
                    f'background-color: {getattr(node, "ui_color", "#ffffff")}; '
                    f'min-width: 120px; z-index: 10; '
                    f'border: 2px solid red; '  # Debug border to make nodes visible
                    f'opacity: 1 !important; '  # Force opacity
                    f'display: block !important; '  # Force display
                    f'position: absolute !important;'  # Force position
                ).props(f'id="node_{node.node_id}"')
                
                with node_card:
                    with ui.column().classes('gap-1 p-2'):
                        ui.label(node.name).classes('font-bold text-sm text-black')
                        ui.label(node.node_id).classes('text-xs text-gray-600')
                        
                        # Add connection points
                        with ui.row().classes('gap-2 mt-2'):
                            ui.button('●', on_click=lambda n=node: self.start_connection(n)).classes('text-xs')
                            ui.button('○', on_click=lambda n=node: self.end_connection(n)).classes('text-xs')
                
                # Make draggable
                node_card.on('click', lambda e, n=node: self.select_node(n))
                
                self.node_panels[node.node_id] = node_card
                print(f"Created UI panel for node {node.node_id} with style: left: {node.ui_posX}px; top: {node.ui_posY}px")
                
                # Force multiple updates to ensure rendering
                node_card.update()
                self.canvas.update()
                if hasattr(self.zoom_container, 'content_container'):
                    self.zoom_container.content_container.update()
                self.zoom_container.update()
                
                # Also schedule an async update
                async def force_update():
                    node_card.update()
                    self.canvas.update()
                    self.zoom_container.update()
                
                ui.timer(0.1, force_update, once=True)
                    
        except Exception as e:
            print(f"ERROR creating node UI: {e}")
            import traceback
            traceback.print_exc()
    
    def move_node_to_position(self, node_id: str, x: float, y: float, use_undo: bool = True):
        """Move a node to a new position."""
        if use_undo:
            self.node_factory.move_node(self.graph, node_id, x, y, use_undo=True)
        else:
            # Direct move (for real-time drag feedback)
            node = self.graph.get_node(node_id)
            if node:
                node.ui_posX = x
                node.ui_posY = y
                
                # Update UI position
                if node_id in self.node_panels:
                    self.node_panels[node_id].style(f'left: {x}px; top: {y}px;')
    
    def select_node(self, node: BaseNode):
        """Select or deselect a node."""
        if node.node_id in self.selected_nodes:
            self.selected_nodes.remove(node.node_id)
        else:
            self.selected_nodes.add(node.node_id)
        
        self.update_selection_display()
        self.update_node_selection_ui()
    
    def delete_selected(self):
        """Delete all selected nodes."""
        if not self.selected_nodes:
            ui.notify('No nodes selected', type='warning')
            return
        
        # Create fence for grouping the deletions
        self.history_manager.add_fence()
        
        for node_id in list(self.selected_nodes):
            self.node_factory.remove_node(self.graph, node_id, use_undo=True)
            
            # Remove UI
            if node_id in self.node_panels:
                self.node_panels[node_id].delete()
                del self.node_panels[node_id]
        
        # Add closing fence
        self.history_manager.add_fence()
        
        self.selected_nodes.clear()
        self.update_all_displays()
        
        ui.notify(f'Deleted nodes', type='positive')
    
    # Connection Operations
    
    def toggle_connection_mode(self):
        """Toggle connection creation mode."""
        self.connection_mode = not self.connection_mode
        self.connection_mode_button.props(f'color={"primary" if self.connection_mode else ""}')
        
        if self.connection_mode:
            ui.notify('Connection mode enabled - click nodes to connect', type='info')
        else:
            ui.notify('Connection mode disabled', type='info')
            self.connection_start = None
    
    def start_connection(self, node: BaseNode):
        """Start a connection from a node."""
        if self.connection_mode:
            self.connection_start = node
            ui.notify(f'Connection started from {node.name}', type='info')
    
    def end_connection(self, node: BaseNode):
        """End a connection at a node."""
        if self.connection_mode and self.connection_start and self.connection_start != node:
            self.create_edge(self.connection_start, node)
            self.connection_start = None
    
    def create_edge(self, source: BaseNode, target: BaseNode):
        """Create an edge between two nodes."""
        edge = Edge(
            edge_type=EdgeType.DATA,
            output_node_id=source.node_id,
            outlet_pin_id="output",
            input_node_id=target.node_id,
            inlet_pin_id="input"
        )
        
        action = AddEdgeAction(self.graph, edge)
        self.history_manager.add_action(action)
        
        self.stats['edges_created'] += 1
        self.update_all_displays()
        
        ui.notify(f'Connected {source.name} to {target.name}', type='positive')
    
    # Undo/Redo Operations
    
    def undo_action(self):
        """Perform undo operation."""
        if self.history_manager.undo():
            self.stats['undo_operations'] += 1
            self.refresh_node_ui()
            self.update_all_displays()
            
            desc = self.history_manager.get_undo_description()
            ui.notify(f'Undid: {desc or "Action"}', type='info')
        else:
            ui.notify('Nothing to undo', type='warning')
    
    def redo_action(self):
        """Perform redo operation."""
        if self.history_manager.redo():
            self.stats['redo_operations'] += 1
            self.refresh_node_ui()
            self.update_all_displays()
            
            desc = self.history_manager.get_redo_description()
            ui.notify(f'Redid: {desc or "Action"}', type='info')
        else:
            ui.notify('Nothing to redo', type='warning')
    
    def clear_graph(self):
        """Clear the entire graph."""
        # Add fence for the clear operation
        self.history_manager.add_fence()
        
        # Remove all nodes
        for node_id in list(self.graph.nodes.keys()):
            self.node_factory.remove_node(self.graph, node_id, use_undo=True)
        
        # Add closing fence
        self.history_manager.add_fence()
        
        # Clear UI
        for panel in self.node_panels.values():
            panel.delete()
        self.node_panels.clear()
        self.selected_nodes.clear()
        
        self.update_all_displays()
        ui.notify('Graph cleared', type='info')
    
    def create_random_graph(self):
        """Create a random test graph."""
        # Add fence for the batch operation
        self.history_manager.add_fence()
        
        node_types = ['test_library:test.math.node', 'test_library:test.source.node', 'test_library:test.sink.node']
        
        # Create random nodes
        created_nodes = []
        for i in range(random.randint(3, 8)):
            node_type = random.choice(node_types)
            x = random.randint(50, 800)
            y = random.randint(50, 600)
            
            try:
                node = self.node_factory.create_node(
                    node_type, 
                    self.graph, 
                    position=(x, y),
                    use_undo=True
                )
                created_nodes.append(node)
                self.create_node_ui(node)
                
            except Exception as e:
                ui.notify(f'Failed to create random node: {e}', type='negative')
        
        # Create some random connections
        if len(created_nodes) >= 2:
            for i in range(random.randint(1, min(len(created_nodes) - 1, 4))):
                source = random.choice(created_nodes)
                target = random.choice([n for n in created_nodes if n != source])
                self.create_edge(source, target)
        
        # Add closing fence
        self.history_manager.add_fence()
        
        self.update_all_displays()
        ui.notify(f'Created random graph with {len(created_nodes)} nodes', type='positive')
    
    # UI Updates
    
    def refresh_node_ui(self):
        """Refresh the node UI to match the current graph state."""
        print(f"Refreshing UI for {len(self.graph.nodes)} nodes")
        
        # Remove all node UI elements
        for panel in self.node_panels.values():
            try:
                panel.delete()
            except:
                pass  # Panel might already be deleted
        self.node_panels.clear()
        
        # Recreate UI for all nodes in the graph
        for node in self.graph.nodes.values():
            print(f"Refreshing UI for node {node.node_id}")
            self.create_node_ui(node)
        
        print(f"Finished refreshing UI. Active panels: {len(self.node_panels)}")
    
    def update_node_selection_ui(self):
        """Update the visual selection state of nodes."""
        for node_id, panel in self.node_panels.items():
            if node_id in self.selected_nodes:
                panel.classes(add='ring-2 ring-blue-500')
            else:
                panel.classes(remove='ring-2 ring-blue-500')
    
    def update_stats_display(self):
        """Update the statistics display."""
        if hasattr(self, 'stats_container'):
            self.stats_container.clear()
            
            with self.stats_container:
                for key, value in self.stats.items():
                    ui.label(f'{key.replace("_", " ").title()}: {value}').classes('text-sm')
                
                # Add factory stats
                factory_stats = self.node_factory.get_factory_stats()
                ui.separator()
                ui.label('Factory Stats:').classes('text-sm font-bold')
                for key, value in factory_stats.items():
                    ui.label(f'{key.replace("_", " ").title()}: {value}').classes('text-xs')
    
    def update_info_display(self):
        """Update the current state information display."""
        if hasattr(self, 'info_container'):
            self.info_container.clear()
            
            with self.info_container:
                ui.label(f'Nodes: {len(self.graph.nodes)}').classes('text-sm')
                ui.label(f'Edges: {len(self.graph.edges)}').classes('text-sm')
                ui.label(f'Selected: {len(self.selected_nodes)}').classes('text-sm')
                
                if self.zoom_container:
                    metrics = getattr(self.zoom_container, 'get_performance_metrics', lambda: {})()
                    if metrics:
                        ui.separator()
                        ui.label(f'Zoom: {metrics.get("current_zoom", 1.0):.2f}').classes('text-xs')
                        ui.label(f'Pan: ({metrics.get("pan_x", 0):.0f}, {metrics.get("pan_y", 0):.0f})').classes('text-xs')
    
    def update_history_display(self):
        """Update the undo history display."""
        if hasattr(self, 'history_container'):
            self.history_container.clear()
            
            with self.history_container:
                history_stats = self.history_manager.get_history_stats()
                
                ui.label(f'History: {history_stats["total_items"]} items').classes('text-sm font-bold')
                ui.label(f'Position: {history_stats["current_index"]}').classes('text-xs')
                
                # Show next undo/redo actions
                undo_desc = self.history_manager.get_undo_description()
                redo_desc = self.history_manager.get_redo_description()
                
                if undo_desc:
                    ui.label(f'← Undo: {undo_desc}').classes('text-xs text-blue-600')
                if redo_desc:
                    ui.label(f'→ Redo: {redo_desc}').classes('text-xs text-green-600')
    
    def update_selection_display(self):
        """Update the selection information display."""
        if hasattr(self, 'selection_container'):
            self.selection_container.clear()
            
            with self.selection_container:
                ui.label(f'Selected Nodes: {len(self.selected_nodes)}').classes('text-sm font-bold')
                
                for node_id in self.selected_nodes:
                    node = self.graph.get_node(node_id)
                    if node:
                        ui.label(f'• {node.name} ({node_id})').classes('text-xs')
    
    def update_all_displays(self):
        """Update all information displays."""
        self.update_stats_display()
        self.update_info_display()
        self.update_history_display()
        self.update_selection_display()
        
        # Update undo/redo button states
        if hasattr(self, 'undo_button'):
            self.undo_button.props(f'disable={not self.history_manager.can_undo()}')
        if hasattr(self, 'redo_button'):
            self.redo_button.props(f'disable={not self.history_manager.can_redo()}')
    
    # Configuration handlers
    
    def toggle_selection_mode(self):
        """Toggle selection mode."""
        ui.notify('Selection mode toggled', type='info')
    
    def toggle_auto_grouping(self, enabled: bool):
        """Toggle auto-grouping configuration."""
        self.undo_config.enable_auto_grouping = enabled
        ui.notify(f'Auto-grouping {"enabled" if enabled else "disabled"}', type='info')
    
    def toggle_action_merging(self, enabled: bool):
        """Toggle action merging configuration."""
        self.undo_config.enable_action_merging = enabled
        ui.notify(f'Action merging {"enabled" if enabled else "disabled"}', type='info')
    
    def set_max_actions(self, max_actions: int):
        """Set maximum number of actions in history."""
        self.undo_config.max_actions = max_actions
        ui.notify(f'Max actions set to {max_actions}', type='info')


def main():
    """Main entry point for the test application."""
    app = UndoRedoTestApp()
    app.create_ui()  # This sets up the page decorator
    
    # Setup periodic updates (will be attached to the page when it loads)
    def update_displays():
        app.update_all_displays()
    
    ui.timer(1.0, update_displays)
    
    ui.run(
        title="Haywire Undo/Redo Test App",
        port=8080,
        reload=True,
        show=True
    )


if __name__ in {"__main__", "__mp_main__"}:
    main()
