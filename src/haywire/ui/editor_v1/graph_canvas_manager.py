"""
GraphCanvasManager - Dedicated UI management for graph visualization

This class manages the visual representation of a graph including nodes and connections.
It handles:
- Node visual creation/removal/positioning
- Connection rendering with SVG paths
- Client-side interaction handling (drag connections, node movement)
- Synchronization with graph data model
- Integration with undo/redo system

The core principle follows condensed.md: delegate real-time interactions to client-side 
JavaScript for smooth UX, while Python manages the data model and finalized state changes.

REFACTORED VERSION: Now uses GraphCanvasVue component instead of embedded JavaScript.
"""

from typing import Dict, List, Optional, Tuple, Callable, Set
from nicegui import ui, events
import json
import uuid
from dataclasses import dataclass

from haywire.core.graph.graph import HaywireGraph, Edge, EdgeType
from haywire.core.node.node import BaseNode
from haywire.ui.utils import generate_pin_id, parse_pin_id, generate_connection_id
from haywire.undo.actions.graph_actions import ChangeSelectionAction, SelectionState, MoveNodeAction, AddEdgeAction, RemoveNodeAction, RemoveEdgeAction, AddNodeAction
from haywire.ui.ui_node import UINode
from haywire.ui.pan_zoom.zoom_pan_vue import ZoomPanContainer
from haywire.ui.editor_v1.graph_canvas_vue import GraphCanvasVue
from haywire.ui.editor_v1.popup_context_menu import PopupContextMenu


@dataclass
class ConnectionDragState:
    """State information during connection creation."""
    is_dragging: bool = False
    start_node_id: Optional[str] = None
    start_port_name: Optional[str] = None
    start_port_type: Optional[str] = None  # 'input' or 'output'


class GraphCanvasManager:
    """
    Manages the visual representation of a graph including nodes and connections.
    
    This refactored version uses a Vue component (GraphCanvasVue) to handle all
    client-side interactions while Python manages the data model.
    
    Responsibilities:
    - Node visual creation/removal/positioning
    - Graph data synchronization
    - Integration with Vue component for UI interactions
    - Event handling and callback management
    """
    
    def __init__(
        self, 
        graph: HaywireGraph,
        node_render_factory,
        history_manager,
        node_factory,
        available_nodes: Optional[List[str]] = None,
        on_graph_changed: Optional[Callable[[], None]] = None,
        session_id: Optional[str] = None,
    ):
        self.graph = graph
        self.node_render_factory = node_render_factory
        self.history_manager = history_manager
        self.node_factory = node_factory
        self.available_nodes = available_nodes or []
        
        # Event callbacks
        self.on_graph_changed = on_graph_changed
        self.session_id = session_id
                
        # Will be created in _setup_canvas()
        self.zoom_container: Optional[ZoomPanContainer] = None
        
        # Visual state
        self.node_panels: Dict[str, Dict] = {}  # node_id -> {ui_node, container, position}
        self.connection_paths: Dict[str, str] = {}  # edge_key -> path_id
        self.selected_nodes: Set[str] = set()
        self.selected_connections: Set[str] = set()
        
        # Sync state - prevents recursive updates during graph sync
        self._syncing = False
        
        # Vue component for canvas interactions
        self.canvas_vue: Optional[GraphCanvasVue] = None
        self.context_menu: Optional[PopupContextMenu] = None
        
        self._setup_canvas()
    
    def _setup_canvas(self):
        """Setup the canvas with Vue component."""
        print("🔧 Setting up GraphCanvasManager with Vue component")
        
        # Create zoom container first
        self.zoom_container = ZoomPanContainer(
            min_zoom=0.1,
            max_zoom=3.0,
            initial_zoom=1.0
        ).classes('w-full flex-grow border-2 border-gray-300').style('height: calc(100% - 60px);')
        
        # Create the Vue-based canvas component inside the zoom container
        with self.zoom_container.content_container:
            self.canvas_vue = GraphCanvasVue(
                zoom_container=self.zoom_container,
                on_connection_created=self._handle_vue_connection_created,
                on_connection_clicked=self._handle_vue_connection_clicked,
                on_node_position_changed=self._handle_vue_node_position_changed,
                on_node_drag_start=self._handle_vue_node_drag_start,
                on_node_drag_end=self._handle_vue_node_drag_end,
                on_selection_changed=self._handle_vue_selection_changed,
                on_context_menu_canvas=self._handle_context_menu_canvas,
                on_context_menu_node=self._handle_context_menu_node,
                on_context_menu_connection=self._handle_context_menu_connection
            )
            
            # Create context menu component
            self.context_menu = PopupContextMenu(
                available_nodes=self.available_nodes,
                on_create_node=self._handle_context_create_node,
                on_duplicate_node=self._handle_context_duplicate_node,
                on_copy_node=self._handle_context_copy_node,
                on_delete_node=self._handle_context_delete_node,
                on_inspect_connection=self._handle_context_inspect_connection,
                on_delete_connection=self._handle_context_delete_connection
            )
    
    @property
    def canvas(self):
        """Backward compatibility property to access the canvas Vue component."""
        return self.canvas_vue
    
    def _handle_vue_connection_created(self, start_node_id: str, start_port: str, end_node_id: str, end_port: str):
        """Handle connection creation from Vue component."""
        try:
            print(f"Connection request: {start_node_id}:{start_port} -> {end_node_id}:{end_port}")
            
            # Create edge directly instead of delegating to app
            edge = Edge(
                edge_type=EdgeType.DATA,
                output_node_id=start_node_id,
                outlet_pin_id=start_port,
                input_node_id=end_node_id,
                inlet_pin_id=end_port
            )
            
            # Create AddEdgeAction directly
            if self.history_manager:
                action = AddEdgeAction(self.graph, edge)
                self.history_manager.add_action(action)
                
                # Notify app to sync other sessions
                if self.on_graph_changed:
                    self.on_graph_changed()
            else:
                # Fallback if no history manager
                self.graph.add_edge(edge)
                
        except Exception as e:
            print(f"Connection creation failed: {e}")
    
    def _handle_vue_connection_clicked(self, path_id: str, edge_data: dict):
        """Handle connection click from Vue component."""
        # Find the corresponding edge from the path_id and trigger removal callback
        for edge_key, stored_path_id in self.connection_paths.items():
            if stored_path_id == path_id:
                # Reconstruct edge from edge_key
                parts = edge_key.split('-')
                if len(parts) >= 4:
                    output_node_id, outlet_pin_id, input_node_id, inlet_pin_id = parts[0], parts[1], parts[2], parts[3]
                    
                    # Find the actual edge object
                    for edge in self.graph.edges:
                        if (edge.output_node_id == output_node_id and edge.outlet_pin_id == outlet_pin_id and
                            edge.input_node_id == input_node_id and edge.inlet_pin_id == inlet_pin_id):
                            
                            # Create RemoveEdgeAction directly instead of delegating to app
                            try:
                                print(f"Connection removal request: {edge.output_node_id} -> {edge.input_node_id}")
                                
                                if self.history_manager:
                                    action = RemoveEdgeAction(self.graph, edge)
                                    self.history_manager.add_action(action)
                                    
                                    # Notify app to sync other sessions
                                    if self.on_graph_changed:
                                        self.on_graph_changed()
                                else:
                                    # Fallback if no history manager
                                    self.graph.remove_edge(
                                        edge.output_node_id, 
                                        edge.outlet_pin_id,
                                        edge.input_node_id, 
                                        edge.inlet_pin_id
                                    )
                                    
                            except Exception as e:
                                print(f"Error removing connection: {e}")
                            break
                break
    
    def _handle_vue_node_position_changed(self, node_id: str, x: float, y: float):
        """Handle node position change from Vue component."""
        # Ignore position changes during sync operations to prevent recursion
        if self._syncing:
            return
        
        # Update stored position when user drags
        if node_id in self.node_panels:
            self.node_panels[node_id]['position'] = (x, y)
        
        # Create MoveNodeAction directly instead of delegating to app
        if node_id in self.graph.nodes:
            node = self.graph.nodes[node_id]
            old_position = (getattr(node, 'ui_posX', 0), getattr(node, 'ui_posY', 0))
            new_position = (x, y)
            
            # Only create an action if the position has actually changed
            if old_position != new_position:
                print(f"DEBUG: Node move - {node_id}: {old_position} -> {new_position}")
                
                if self.history_manager:
                    # Create MoveNodeAction directly
                    action = MoveNodeAction(self.graph, node_id, x, y)
                    self.history_manager.add_action(action)
                    
                    # Notify app to sync other sessions
                    if self.on_graph_changed:
                        self.on_graph_changed()
                else:
                    # Fallback if no history manager
                    node.ui_posX, node.ui_posY = new_position
    
    def _handle_vue_node_drag_start(self, node_id: str):
        """Handle node drag start from Vue component - add fence for undo grouping."""
        print(f"[GraphCanvasManager] Node drag started: {node_id}")
        
        # Add fence to group all drag-related actions together
        self.history_manager.add_fence()
        print(f"[GraphCanvasManager] Added fence for drag start: {node_id}")
    
    def _handle_vue_node_drag_end(self, node_id: str, position_changed: bool):
        """Handle node drag end from Vue component - add fence to end grouping."""
        print(f"[GraphCanvasManager] Node drag ended: {node_id}, position changed: {position_changed}")
        
        # Add fence to end the drag operation grouping
        if position_changed:
            self.history_manager.add_fence()
            print(f"[GraphCanvasManager] Added fence for drag end: {node_id}")
        else:
            print(f"[GraphCanvasManager] No fence needed - position unchanged for: {node_id}")
    
    def _handle_vue_selection_changed(self, selected_nodes: List[str], selected_connections: List[str]):
        """Handle selection changes from Vue component."""
        print(f"🎯 Selection changed from Vue: nodes={selected_nodes}, connections={selected_connections}")
        
        # Ignore selection changes during sync operations to prevent recursion
        if self._syncing:
            return
        
        # Create new selection state
        selected_nodes_set = set(selected_nodes)
        selected_connections_set = set(selected_connections)
        
        # Convert connection IDs to edge tuples for SelectionState format
        selected_edges = set()
        for connection_id in selected_connections_set:
            # Parse connection ID format: connection__outlet__node_id__port__inlet__node_id__port
            try:
                parts = connection_id.split('__')
                if len(parts) >= 6 and parts[0] == 'connection' and parts[1] == 'outlet' and parts[4] == 'inlet':
                    output_node_id = parts[2]
                    outlet_pin = parts[3]
                    input_node_id = parts[5]
                    inlet_pin = parts[6]
                    selected_edges.add((output_node_id, outlet_pin, input_node_id, inlet_pin))
            except (IndexError, ValueError):
                # Skip invalid connection IDs
                continue
        
        new_selection = SelectionState(selected_nodes_set, selected_edges)
        
        # Create and execute undo action
        action = ChangeSelectionAction(self.graph, new_selection)
        self.history_manager.add_action(action)
        
        # Update local state for fast access (this will be in sync with graph state)
        self.selected_nodes = selected_nodes_set
        self.selected_connections = selected_connections_set
        
        # Notify app to sync other sessions
        if self.on_graph_changed:
            self.on_graph_changed()
        
    # Node Management
    def add_node_visual(self, node: BaseNode, position: Tuple[float, float] = (100, 100)) -> bool:
        """Add a visual representation of a node to the canvas."""
        try:
            x, y = position
            print(f"Adding node visual for {node.node_id} at position ({x}, {y})")
            
            with self.canvas_vue:
                with ui.column().classes('absolute').style(
                    f'left: {x}px; top: {y}px; z-index: 100;'
                ).props(f'id="{node.node_id}" data-node-id="{node.node_id}"') as container:
                    
                    print(f"Created container for node {node.node_id}")
                    
                    # Use UINode for proper rendering
                    ui_node = UINode(node, self.node_render_factory, container)
                    ui_node.render()
                    print(f"Rendered UINode for {node.node_id}")
                    
                    # Store reference
                    self.node_panels[node.node_id] = {
                        'ui_node': ui_node,
                        'container': container,
                        'position': position
                    }
                    
                    # Setup observers for this node via Vue component
                    if self.canvas_vue:
                        self.canvas_vue.add_node_observer(node.node_id)
                        print(f"Setup Vue observers for {node.node_id}")
            
            print(f"Successfully added node visual for {node.node_id}")
            return True
            
        except RuntimeError as e:
            if "client this element belongs to has been deleted" in str(e):
                # Re-raise client deletion errors so they can be caught by sync_all_sessions
                print(f"Error adding node visual: {e}")
                raise
            else:
                print(f"Runtime error adding node visual: {e}")
                import traceback
                traceback.print_exc()
                return False
        except Exception as e:
            print(f"Error adding node visual: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def remove_node_visual(self, node_id: str) -> bool:
        """Remove a node's visual representation."""
        if node_id not in self.node_panels:
            return False
            
        try:
            # Remove all connected edges visually first
            edges_to_remove = []
            for edge in self.graph.edges:
                if edge.input_node_id == node_id or edge.output_node_id == node_id:
                    edge_key = self._get_edge_key(edge)
                    edges_to_remove.append(edge_key)
            
            for edge_key in edges_to_remove:
                self.remove_connection_visual(edge_key)
            
            # Remove node visual
            visual_data = self.node_panels[node_id]
            
            if 'ui_node' in visual_data:
                ui_node = visual_data['ui_node']
                if hasattr(ui_node, 'cleanup'):
                    ui_node.cleanup()
            
            visual_data['container'].delete()
            del self.node_panels[node_id]
            
            # Remove from selection
            self.selected_nodes.discard(node_id)
            
            # Remove observers via Vue component
            if self.canvas_vue:
                self.canvas_vue.remove_node_observer(node_id)
            
            return True
            
        except Exception as e:
            print(f"Error removing node visual: {e}")
            return False
    
    def update_node_position(self, node_id: str, position: Tuple[float, float]):
        """Update a node's visual position."""
        if node_id not in self.node_panels:
            return
            
        x, y = position
        container = self.node_panels[node_id]['container']
        
        # Update the style using NiceGUI's update mechanism
        container.style(f'left: {x}px; top: {y}px; z-index: 100;')
        container.update()  # Force update to propagate to all clients
        
        self.node_panels[node_id]['position'] = position
        
        # Also try the force update method as backup
        if self.canvas_vue:
            self.canvas_vue.update_connections_for_node(node_id)
        container = self.node_panels[node_id]['container']
        container.style(f'left: {x}px; top: {y}px;')
        self.node_panels[node_id]['position'] = position
    
    # Connection Management
    def _get_edge_key(self, edge: Edge) -> str:
        """Generate a unique key for an edge using Format 2."""
        return generate_connection_id(
            edge.output_node_id, 
            edge.outlet_pin_id, 
            edge.input_node_id, 
            edge.inlet_pin_id
        )
    
    def add_connection_visual(self, edge: Edge) -> bool:
        """Add a visual connection between two nodes."""
        print(f"🔗 Python: Adding connection visual for {edge.output_node_id}:{edge.outlet_pin_id} -> {edge.input_node_id}:{edge.inlet_pin_id}")
        try:
            edge_key = self._get_edge_key(edge)
            
            # Use Vue component to add connection visual
            if self.canvas_vue:
                # Create pin IDs in the expected format
                from_pin_id = f"{edge.output_node_id}:{edge.outlet_pin_id}"
                to_pin_id = f"{edge.input_node_id}:{edge.inlet_pin_id}"
                connection_id = edge_key  # Use edge key as connection ID
                
                self.canvas_vue.add_connection_visual(connection_id, from_pin_id, to_pin_id)
                self.connection_paths[edge_key] = connection_id
                print(f"🔗 Python: Created connection via Vue component with ID: {connection_id}")
                return True
            else:
                print(f"❌ Vue component not available")
                return False
        except RuntimeError as e:
            if "client this element belongs to has been deleted" in str(e):
                # Re-raise client deletion errors so they can be caught by sync_all_sessions
                print(f"🔗 Error adding connection visual: {e}")
                raise
            else:
                print(f"🔗 Runtime error adding connection visual: {e}")
                import traceback
                traceback.print_exc()
                return False
        except Exception as e:
            print(f"🔗 Error adding connection visual: {e}")
            import traceback
            traceback.print_exc()
            return False
            
        except Exception as e:
            print(f"Error adding connection visual: {e}")
            return False
    
    def remove_connection_visual(self, edge_key: str) -> bool:
        """Remove a connection's visual representation."""
        if edge_key not in self.connection_paths:
            return False
            
        try:
            path_id = self.connection_paths[edge_key]
            
            # Use Vue component to remove connection visual
            if self.canvas_vue:
                success = self.canvas_vue.remove_connection_visual(path_id)
                if success:
                    del self.connection_paths[edge_key]
                    return True
            
            return False
        except Exception as e:
            print(f"Error removing connection visual: {e}")
            return False
    
    def _on_connection_clicked(self, edge: Edge):
        """Handle connection click events."""
        print(f"Connection clicked: {edge.output_node_id} -> {edge.input_node_id}")
        if self.on_connection_removed:
            self.on_connection_removed(edge)
    
    # Graph Synchronization
    def sync_with_graph(self):
        """Synchronize visual representation with the graph state."""
        # Set sync flag to prevent recursive updates
        self._syncing = True
        
        try:
            # Sync nodes
            graph_node_ids = set(self.graph.nodes.keys())
            visual_node_ids = set(self.node_panels.keys())
            
            # Add missing nodes
            for node_id in graph_node_ids - visual_node_ids:
                node = self.graph.nodes[node_id]
                position = (
                    getattr(node, 'ui_posX', 100),
                    getattr(node, 'ui_posY', 100)
                )
                self.add_node_visual(node, position)
            
            # Remove extra nodes
            for node_id in visual_node_ids - graph_node_ids:
                self.remove_node_visual(node_id)
                
            # Update positions of existing nodes
            for node_id in graph_node_ids.intersection(visual_node_ids):
                node = self.graph.nodes[node_id]
                new_position = (
                    getattr(node, 'ui_posX', 100),
                    getattr(node, 'ui_posY', 100)
                )
                old_position = self.node_panels[node_id]['position']
                
                # Only update if position has changed
                if new_position != old_position:
                    print(f"Updating node {node_id} position: {old_position} -> {new_position}")
                    self.update_node_position(node_id, new_position)
            
            # Sync connections - use Vue component's reactive prop system
            if self.canvas_vue:
                # Pass all edges to Vue component, let it handle the diff
                self.canvas_vue.sync_connections_from_edges(self.graph.edges)
                
                # Also update our connection_paths dictionary to keep it in sync
                # This is needed for selection management
                new_connection_paths = {}
                for edge in self.graph.edges:
                    edge_key = self._get_edge_key(edge)
                    connection_id = edge_key  # Use edge key as connection ID (consistent with add_connection_visual)
                    new_connection_paths[edge_key] = connection_id
                
                # Update the connection_paths dictionary
                self.connection_paths = new_connection_paths
                print(f"🔄 Updated connection_paths dictionary with {len(self.connection_paths)} connections")
            else:
                # Fallback to individual connection management
                graph_edge_keys = set(self._get_edge_key(edge) for edge in self.graph.edges)
                visual_edge_keys = set(self.connection_paths.keys())
                
                # Add missing connections
                for edge in self.graph.edges:
                    edge_key = self._get_edge_key(edge)
                    if edge_key not in visual_edge_keys:
                        self.add_connection_visual(edge)
                
                # Remove extra connections
                for edge_key in visual_edge_keys - graph_edge_keys:
                    self.remove_connection_visual(edge_key)
            
            # Sync selection state from graph to UI using existing methods
            graph_selected_nodes, graph_selected_connections = self.graph.get_selection_state()
            
            # Clear current UI selection (this also updates the Vue component)
            self.clear_selection()
            
            # Rebuild selection using existing methods (these also update the Vue component)
            for node_id in graph_selected_nodes:
                self.select_node(node_id, multi_select=True)
            
            for connection_id in graph_selected_connections:
                self.select_connection(connection_id, multi_select=True)
                
            print(f"🔄 Selection synced from graph: {len(graph_selected_nodes)} nodes, {len(graph_selected_connections)} connections")
        finally:
            # Always clear sync flag
            self._syncing = False
    
    def clear_all_visuals(self):
        """Clear all visual representations."""
        # Clear nodes
        for node_id in list(self.node_panels.keys()):
            self.remove_node_visual(node_id)
        
        # Clear connections
        for edge_key in list(self.connection_paths.keys()):
            self.remove_connection_visual(edge_key)
        
        # Clear selection
        self.selected_nodes.clear()
        self.selected_connections.clear()
    
    # Selection Management
    def select_node(self, node_id: str, multi_select: bool = False):
        """Select a node."""
        if not multi_select:
            self.selected_nodes.clear()
        
        self.selected_nodes.add(node_id)
        
        # Update visual selection in Vue component
        if self.canvas_vue:
            try:
                self.canvas_vue.select_node(node_id, multi_select)
            except (AttributeError, RuntimeError) as e:
                print(f"Warning: Could not update visual selection for node {node_id}: {e}")
    
    def deselect_node(self, node_id: str):
        """Deselect a node."""
        self.selected_nodes.discard(node_id)
        
        # Update visual selection in Vue component
        if self.canvas_vue:
            try:
                self.canvas_vue.deselect_node(node_id)
            except (AttributeError, RuntimeError) as e:
                print(f"Warning: Could not update visual deselection for node {node_id}: {e}")
    
    def select_connection(self, edge_key: str, multi_select: bool = False):
        """Select a connection."""
        if not multi_select:
            self.selected_connections.clear()
        
        self.selected_connections.add(edge_key)
        
        # Update visual selection in Vue component
        if self.canvas_vue and edge_key in self.connection_paths:
            try:
                path_id = self.connection_paths[edge_key]
                self.canvas_vue.select_connection(path_id, multi_select)
            except (AttributeError, RuntimeError) as e:
                print(f"Warning: Could not update visual selection for connection {edge_key}: {e}")
        
        print(f"🎯 Selected connection: {edge_key}")
    
    def deselect_connection(self, edge_key: str):
        """Deselect a connection."""
        self.selected_connections.discard(edge_key)
        
        # Update visual selection in Vue component
        if self.canvas_vue and edge_key in self.connection_paths:
            try:
                path_id = self.connection_paths[edge_key]
                self.canvas_vue.deselect_connection(path_id)
            except (AttributeError, RuntimeError) as e:
                print(f"Warning: Could not update visual deselection for connection {edge_key}: {e}")
        
        print(f"🎯 Deselected connection: {edge_key}")
    
    def clear_selection(self):
        """Clear all selections."""
        self.selected_nodes.clear()
        self.selected_connections.clear()
        
        # Update visual selection in Vue component
        if self.canvas_vue:
            try:
                self.canvas_vue.clear_selection()
            except (AttributeError, RuntimeError) as e:
                print(f"Warning: Could not clear visual selection: {e}")
        
        print("🎯 Cleared all selections")
    
    def get_selected_nodes(self) -> Set[str]:
        """Get currently selected nodes."""
        return self.selected_nodes.copy()
    
    def get_selected_connections(self) -> Set[str]:
        """Get currently selected connections."""
        return self.selected_connections.copy()
    
    # Cleanup
    # Note: update_zoom_pan_state method removed - zoom/pan is handled by CSS transforms
    # in the zoom container, so no manual state sync or connection updates needed
    
    def cleanup(self):
        """Cleanup resources."""
        self.clear_all_visuals()
        if self.canvas_vue:
            self.canvas_vue.cleanup()
        self.canvas_vue = None
        self.context_menu = None
        self.node_render_factory = None
        self.graph = None
    
    # Context Menu Event Handlers
    
    def _handle_context_menu_canvas(self, screen_x: float, screen_y: float, canvas_x: float, canvas_y: float):
        """Handle canvas context menu request."""
        print(f"🎯 Canvas context menu requested at screen({screen_x}, {screen_y}) canvas({canvas_x}, {canvas_y})")
        if self.context_menu:
            self.context_menu.show_canvas_menu(screen_x, screen_y, canvas_x, canvas_y)
    
    def _handle_context_menu_node(self, node_id: str, x: float, y: float):
        """Handle node context menu request."""
        print(f"🎯 Node context menu requested for {node_id} at ({x}, {y})")
        if self.context_menu:
            self.context_menu.show_node_menu(x, y, node_id)
    
    def _handle_context_menu_connection(self, connection_id: str, x: float, y: float):
        """Handle connection context menu request."""
        print(f"🎯 Connection context menu requested for {connection_id} at ({x}, {y})")
        if self.context_menu:
            self.context_menu.show_connection_menu(x, y, connection_id)
    
    # Context Menu Action Handlers
    
    def _handle_context_create_node(self, node_type: str, x: float, y: float):
        """Handle node creation from context menu."""
        print(f"📝 Creating node {node_type} at ({x}, {y}) from context menu")
        
        try:
            # Create node using the injected factory
            node = self.node_factory.create_instance(
                node_type,
                self.graph,  # Pass the graph to the factory
                position=(x, y)
            )
            
            if node:
                # Set position attributes
                node.ui_posX = x
                node.ui_posY = y
                
                # Create AddNodeAction directly
                if self.history_manager:
                    action = AddNodeAction(self.graph, node)
                    self.history_manager.add_action(action)
                    
                    # Notify app to sync other sessions
                    if self.on_graph_changed:
                        self.on_graph_changed()
                else:
                    # Fallback if no history manager
                    self.graph.add_node(node)
                
                print(f"✅ Created node {node.node_id} at ({x}, {y})")
            else:
                from nicegui import ui
                ui.notify(f"Failed to create node of type: {node_type}", type='negative')
                
        except Exception as e:
            print(f"Error creating node: {e}")
            from nicegui import ui
            ui.notify(f"Error creating node: {e}", type='negative')
    
    def _handle_context_duplicate_node(self, node_id: str):
        """Handle node duplication from context menu."""
        print(f"📋 Duplicating node {node_id} from context menu")
        from nicegui import ui
        ui.notify(f"Duplicating node {node_id}")
        # TODO: Implement node duplication logic
    
    def _handle_context_copy_node(self, node_id: str):
        """Handle node copy from context menu."""
        print(f"📄 Copying node {node_id} from context menu")
        from nicegui import ui
        ui.notify(f"Copied node {node_id}")
        # TODO: Implement node copy logic
    
    def _handle_context_delete_node(self, node_id: str):
        """Handle node deletion from context menu."""
        print(f"🗑️ Deleting node {node_id} from context menu")
        from nicegui import ui
        
        if node_id in self.graph.nodes:
            try:
                # Use history manager to remove node with undo support
                node = self.graph.nodes[node_id]
                action = RemoveNodeAction(self.graph, node_id, node)
                self.history_manager.add_action(action)
                
                # Sync visual representation
                self.sync_with_graph()
                ui.notify(f"Deleted node {node_id}")
                
            except Exception as e:
                print(f"Error deleting node: {e}")
                ui.notify(f"Error deleting node: {e}", type='negative')
        else:
            ui.notify(f"Node {node_id} not found", type='warning')
    
    def _handle_context_inspect_connection(self, connection_id: str):
        """Handle connection inspection from context menu."""
        print(f"🔍 Inspecting connection {connection_id} from context menu")
        from nicegui import ui
        ui.notify(f"Inspecting connection {connection_id}")
        # TODO: Show connection details dialog
    
    def _handle_context_delete_connection(self, connection_id: str):
        """Handle connection deletion from context menu."""
        print(f"🗑️ Deleting connection {connection_id} from context menu")
        from nicegui import ui
        
        # Find the edge by connection_id
        edge_to_remove = None
        for edge in self.graph.edges:
            edge_key = self._get_edge_key(edge)
            if edge_key == connection_id:
                edge_to_remove = edge
                break
        
        if edge_to_remove:
            try:
                # Create and execute undo action
                action = RemoveEdgeAction(self.graph, edge_to_remove, f"Delete connection from context menu")
                self.history_manager.add_action(action)
                
                # Sync visual representation
                self.sync_with_graph()
                ui.notify(f"Deleted connection")
                    
            except Exception as e:
                print(f"Error deleting connection: {e}")
                ui.notify(f"Error deleting connection: {e}", type='negative')
        else:
            ui.notify(f"Connection not found", type='warning')
    
    def update_available_nodes(self, nodes: List[str]):
        """Update the list of available nodes for context menu."""
        self.available_nodes = nodes
        if self.context_menu:
            self.context_menu.update_available_nodes(nodes)
        
    # Zoom control convenience methods
    def zoom_to_fit(self):
        """Zoom to fit all content."""
        if self.zoom_container:
            self.zoom_container.fit_to_content()
    
    def reset_zoom(self):
        """Reset zoom to initial value."""
        if self.zoom_container:
            self.zoom_container.reset_view()
    
    def zoom_in(self):
        """Zoom in."""
        if self.zoom_container:
            self.zoom_container.zoom_in()
    
    def zoom_out(self):
        """Zoom out."""
        if self.zoom_container:
            self.zoom_container.zoom_out()
    
    @property
    def current_zoom(self) -> float:
        """Get current zoom level."""
        return self.zoom_container.current_zoom if self.zoom_container else 1.0
    
    @property
    def pan_x(self) -> float:
        """Get current pan X position."""
        return self.zoom_container.pan_x if self.zoom_container else 0.0
    
    @property
    def pan_y(self) -> float:
        """Get current pan Y position."""
        return self.zoom_container.pan_y if self.zoom_container else 0.0


# Deprecated global callback registry - no longer needed with Vue component
_canvas_managers: Dict[str, GraphCanvasManager] = {}

def register_canvas_manager(manager: GraphCanvasManager):
    """Register a canvas manager for JavaScript callbacks."""
    # No longer needed - Vue component handles callbacks
    pass

def unregister_canvas_manager(manager: GraphCanvasManager):
    """Unregister a canvas manager."""
    # No longer needed - Vue component handles callbacks
    pass
