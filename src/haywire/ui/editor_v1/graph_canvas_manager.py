"""
GraphCanvasManager - Enhanced with class-based event system

ENHANCED VERSION: Now uses auto-registration event handlers with type-safe event classes.
This eliminates complex callback management and provides compile-time safety.
"""

import traceback
from typing import Dict, List, Optional, Tuple, Callable, Set
from nicegui import ui, events
from dataclasses import dataclass

from haywire.core.graph.graph import HaywireGraph, Edge, EdgeType
from haywire.core.node.node import BaseNode
from haywire.ui.utils import generate_pin_id, parse_pin_id, generate_connection_id
from haywire.undo.actions.graph_actions import ChangeSelectionAction, SelectionState, MoveNodeAction, AddEdgeAction, RemoveNodeAction, RemoveEdgeAction, AddNodeAction
from haywire.ui.ui_node import UINode
from haywire.ui.pan_zoom.zoom_pan_vue import ZoomPanContainer

from .graph_canvas_vue import GraphCanvasVue
from .popup_context_menu import PopupContextMenu
from .event_definitions import *
from .event_handlers import handles_event


@dataclass
class ConnectionDragState:
    """State information during connection creation."""
    is_dragging: bool = False
    start_node_id: Optional[str] = None
    start_port_name: Optional[str] = None
    start_port_type: Optional[str] = None  # 'input' or 'output'


class GraphCanvasManager:
    """
    Enhanced graph canvas manager with class-based event system.
    
    This version uses auto-registration event handlers with type-safe event classes,
    eliminating complex callback management while maintaining all existing functionality.
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
        self.session_id = session_id or "default"
                
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
        
        # Enhanced event handling system
        self._event_handlers: Dict[str, Callable] = {}
        self._auto_register_event_handlers()
        
        self._setup_canvas()
    
    def _auto_register_event_handlers(self):
        """Automatically register event handlers using decorators"""
        print("🔧 Auto-registering event handlers...")
        
        for method_name in dir(self):
            method = getattr(self, method_name)
            if hasattr(method, '_handles_event_classes'):
                for event_class in method._handles_event_classes:
                    event_type = event_class.event_type
                    self._event_handlers[event_type] = method
                    print(f"✅ Registered: {event_class.__name__} → {method_name}")
        
        # Verify all user events have handlers
        self._validate_handler_coverage()
    
    def _validate_handler_coverage(self):
        """Ensure all user events have registered handlers"""
        user_events = [event_type for event_type, event_class in GRAPH_EVENT_REGISTRY.items() 
                      if getattr(event_class, 'category', 'user') == 'user']
        
        missing_handlers = []
        for event_type in user_events:
            if event_type not in self._event_handlers:
                missing_handlers.append(event_type)
        
        if missing_handlers:
            print(f"⚠️  Missing handlers for events: {missing_handlers}")
        else:
            print(f"✅ All {len(user_events)} user events have registered handlers")
    
    def _setup_canvas(self):
        """Setup canvas with enhanced event system."""
        print("🔧 Setting up GraphCanvasManager with enhanced events")
        
        # Create zoom container
        self.zoom_container = ZoomPanContainer(
            min_zoom=0.1,
            max_zoom=3.0,
            initial_zoom=1.0
        ).classes('w-full flex-grow border-2 border-gray-300').style('height: calc(100% - 60px);')
        
        with self.zoom_container.content_container:
            self.canvas_vue = GraphCanvasVue(
                zoom_container=self.zoom_container,
                on_canvas_event=self._handle_canvas_event
            )
            
            self.context_menu = PopupContextMenu(
                available_nodes=self.available_nodes,
                on_emit_event=self._handle_canvas_event  # New event system
            )

    def _handle_canvas_event(self, event: BaseGraphEvent):
        """
        Unified canvas event router using auto-registered handlers
        """
        event_type = event.event_type
        handler = self._event_handlers.get(event_type)
        
        if handler:
            print(f"🔧 Calling handler for {event_type}: {handler.__name__}")
            try:
                # Just call the handler with the event - all our handlers expect (self, event)
                handler(event)
            except Exception as e:
                print(f"❌ Error calling handler for {event_type}: {e}")
                ui.notify(f"Error while processing {event.description}: {e}", type='negative')
                traceback.print_exc()
        else:
            print(f"No handler found for event type: {event_type}")
    
    # =============================================================================
    # EVENT HANDLERS (Auto-registered via decorators)
    # =============================================================================
    
                            
    @handles_event(ConnectionCreatedEvent)
    def process_connection_creation(self, event: ConnectionCreatedEvent):
        """Handle connection creation"""
        print(f"Creating connection: {event.outputNodeId}:{event.outletPinId} -> {event.inputNodeId}:{event.inletPinId}")
        
        # Create edge in graph
        edge = Edge(
            edge_type=EdgeType.DATA,
            output_node_id=event.outputNodeId,
            outlet_pin_id=event.outletPinId,
            input_node_id=event.inputNodeId,
            inlet_pin_id=event.inletPinId
        )
        
        # Add to graph
        action = AddEdgeAction(self.graph, edge)
        self.history_manager.add_action(action)
        
        # Always broadcast local user interactions to other sessions
        # (The requires_broadcast flag is metadata, not part of the event object)
        if self.on_graph_changed:
            self.on_graph_changed()
                
    @handles_event(ConnectionRemovedEvent)
    def process_connection_deletion(self, event: ConnectionRemovedEvent):
        """Handle connection deletion from context menu."""
        connection_id = event.connectionId
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
            # Create and execute undo action
            action = RemoveEdgeAction(self.graph, edge_to_remove, f"Delete connection from context menu")
            self.history_manager.add_action(action)
            
            # Always broadcast local user interactions to other sessions
            # (The requires_broadcast flag is metadata, not part of the event object)
            if self.on_graph_changed:
                self.on_graph_changed()
            ui.notify(f"Deleted connection")                    
        else:
            ui.notify(f"Connection not found", type='warning')

    @handles_event(ConnectionClickedEvent)
    def process_connection_click(self, event: ConnectionClickedEvent):
        """Handle connection click events - remove the connection"""
        try:
            print(f"Connection clicked for removal: {event.connectionId}")
            
            # Find the corresponding edge from the connection ID
            for edge_key, stored_path_id in self.connection_paths.items():
                if stored_path_id == event.connectionId:
                    # Reconstruct edge from edge_key
                    parts = edge_key.split('-')
                    if len(parts) >= 4:
                        output_node_id, outlet_pin_id, input_node_id, inlet_pin_id = parts[0], parts[1], parts[2], parts[3]
                        
                        # Find the actual edge object
                        for edge in self.graph.edges:
                            if (edge.output_node_id == output_node_id and edge.outlet_pin_id == outlet_pin_id and
                                edge.input_node_id == input_node_id and edge.inlet_pin_id == inlet_pin_id):
                                
                                # Create RemoveEdgeAction
                                action = RemoveEdgeAction(self.graph, edge)
                                self.history_manager.add_action(action)
                                
                                # Always broadcast local user interactions to other sessions
                                # (The requires_broadcast flag is metadata, not part of the event object)
                                if self.on_graph_changed:
                                    self.on_graph_changed()
                                break
                    break
                    
        except Exception as e:
            print(f"Connection click handling failed: {e}")
    
    @handles_event(NodeDragStartEvent)
    def process_node_drag_start(self, event: NodeDragStartEvent):
        """Handle node drag start"""
        print(f"Node drag started: {event.nodeId}")
        
        # Add fence to group all drag-related actions together
        self.history_manager.add_fence()
    
    @handles_event(NodeDragEndEvent)
    def process_node_drag_end(self, event: NodeDragEndEvent):
        """Handle node drag end"""
        print(f"Node drag ended: {event.nodeId}, position changed: {event.positionChanged}")
        
        # Add fence to end the drag operation grouping
        if event.positionChanged:
            self.history_manager.add_fence()

    @handles_event(NodePositionChangedEvent)
    def process_node_position_change(self, event: NodePositionChangedEvent):
        """Handle node position updates"""
        print(f"Updating node position: {event.nodeId} to ({event.position['x']}, {event.position['y']})")
        
        # Ignore position changes during sync operations to prevent recursion
        if self._syncing:
            return
        
        # Update stored position when user drags
        if event.nodeId in self.node_panels:
            self.node_panels[event.nodeId]['position'] = (event.position['x'], event.position['y'])
        
        # Create MoveNodeAction directly
        if event.nodeId in self.graph.nodes:
            node = self.graph.nodes[event.nodeId]
            old_position = (getattr(node, 'ui_posX', 0), getattr(node, 'ui_posY', 0))
            new_position = (event.position['x'], event.position['y'])
            
            # Only create an action if the position has actually changed
            if old_position != new_position:
                action = MoveNodeAction(self.graph, event.nodeId, event.position['x'], event.position['y'])
                self.history_manager.add_action(action)
                
                # Always broadcast local user interactions to other sessions
                # (The requires_broadcast flag is metadata, not part of the event object)
                if self.on_graph_changed:
                    self.on_graph_changed()

    @handles_event(SelectionChangedEvent)
    def process_selection_change(self, event: SelectionChangedEvent):
        """Handle selection changes"""
        print(f"Selection changed: nodes={event.selectedNodes}, connections={event.selectedConnections}")
        
        # Ignore selection changes during sync operations to prevent recursion
        if self._syncing:
            return
        
        # Create new selection state
        selected_nodes_set = set(event.selectedNodes)
        selected_connections_set = set(event.selectedConnections)
        
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
        
        # Update local state for fast access
        self.selected_nodes = selected_nodes_set
        self.selected_connections = selected_connections_set
        
        # Always broadcast local user interactions to other sessions
        # (The requires_broadcast flag is metadata, not part of the event object)
        if self.on_graph_changed:
            self.on_graph_changed()
    
    @handles_event(ContextMenuCanvasEvent, ContextMenuNodeEvent, ContextMenuConnectionEvent)
    def process_context_menu(self, event):
        """Handle context menu events"""
        if isinstance(event, ContextMenuCanvasEvent):
            print(f"Canvas context menu at ({event.screenX}, {event.screenY})")
            if self.context_menu:
                self.context_menu.show_canvas_menu(event.screenX, event.screenY, event.canvasX, event.canvasY)
            
        elif isinstance(event, ContextMenuNodeEvent):
            print(f"Node context menu for {event.nodeId} at ({event.screenX}, {event.screenY})")
            if self.context_menu:
                self.context_menu.show_node_menu(event.screenX, event.screenY, event.nodeId)
            
        elif isinstance(event, ContextMenuConnectionEvent):
            print(f"Connection context menu for {event.connectionId} at ({event.screenX}, {event.screenY})")
            if self.context_menu:
                self.context_menu.show_connection_menu(event.screenX, event.screenY, event.connectionId)
    
    @handles_event(NodeCreateRequestEvent)
    def process_node_creation_request(self, event: NodeCreateRequestEvent):
        """Handle node creation requests from context menu or other sources."""
        print(f"📝 Processing node creation request: {event.nodeType} at ({event.position['x']}, {event.position['y']})")
        
        try:
            # Create node using the injected factory
            node = self.node_factory.create_instance(
                event.nodeType,
                self.graph,  # Pass the graph to the factory
                position=(event.position['x'], event.position['y'])
            )
            
            if node:
                # Set position attributes
                node.ui_posX = event.position['x']
                node.ui_posY = event.position['y']
                
                action = AddNodeAction(self.graph, node)
                self.history_manager.add_action(action)
                
                # Always broadcast to other sessions for locally-created nodes
                # (The requires_broadcast flag is metadata, not part of the event object)
                if self.on_graph_changed:
                    self.on_graph_changed()
                
                print(f"✅ Created node {node.node_id} at ({event.position['x']}, {event.position['y']})")
                ui.notify(f"Created {event.nodeType} node", type='positive')
            else:
                ui.notify(f"Failed to create node of type: {event.nodeType}", type='negative')
                
        except Exception as e:
            print(f"Error creating node: {e}")
            ui.notify(f"Error creating node: {e}", type='negative')

    @handles_event(NodeRemoveRequestEvent)
    def process_node_deletion_request(self, event: NodeRemoveRequestEvent):
        """Handle node deletion from context menu."""
        print(f"🗑️ Deleting node {event.nodeId} from context menu")

        if event.nodeId in self.graph.nodes:
            # Use history manager to remove node with undo support
            node = self.graph.nodes[event.nodeId]
            action = RemoveNodeAction(self.graph, event.nodeId, node)
            self.history_manager.add_action(action)
            
            # Always broadcast local user interactions to other sessions
            # (The requires_broadcast flag is metadata, not part of the event object)
            if self.on_graph_changed:
                self.on_graph_changed()
            ui.notify(f"Deleted node {event.nodeId}")
            
        else:
            ui.notify(f"Node {event.nodeId} not found", type='warning')


    # =============================================================================
    # SYNC EVENT BROADCASTING
    # =============================================================================
    
    def _broadcast_sync_event(self, sync_event: BaseGraphEvent, exclude_session: str = None):
        """Broadcast sync event to all other sessions"""
        # Implementation depends on your session management system
        # This is a placeholder for the actual broadcasting logic
        
        # For now, just emit to the current session's Vue component for testing
        if self.canvas_vue and exclude_session != self.session_id:
            try:
                self.canvas_vue.emit_sync_event(sync_event)
            except Exception as e:
                print(f"Error broadcasting sync event: {e}")

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
            
            # Sync connections - use incremental updates for better performance
            if self.canvas_vue:
                current_edge_keys = set(self.connection_paths.keys())
                graph_edge_keys = set()
                
                # Add or update connections from graph
                for edge in self.graph.edges:
                    edge_key = self._get_edge_key(edge)
                    graph_edge_keys.add(edge_key)
                    
                    # Add new connections that don't exist visually
                    if edge_key not in current_edge_keys:
                        print(f"🔄 Adding new connection: {edge_key}")
                        self.add_connection_visual(edge)
                
                # Remove connections no longer in graph
                connections_to_remove = current_edge_keys - graph_edge_keys
                for edge_key in connections_to_remove:
                    print(f"🔄 Removing old connection: {edge_key}")
                    self.remove_connection_visual(edge_key)
                
                print(f"🔄 Incremental connection sync: {len(graph_edge_keys)} total connections")
            
            # Sync selection state from graph to UI using existing methods
            graph_selected_nodes, graph_selected_connections = self.graph.get_selection_state()
            
            # Clear current UI selection (this also updates the Vue component)
            self.clear_selection()
            
            # Rebuild selection using existing methods (these also update the Vue component)
            for node_id in graph_selected_nodes:
                self.select_node(node_id, multi_select=True)
            
            for connection_id in graph_selected_connections:
                self.select_connection(connection_id, multi_select=True)

            self.canvas_vue.update()  # Force Vue component to refresh
                
            print(f"🔄 Selection synced from graph: {len(graph_selected_nodes)} nodes, {len(graph_selected_connections)} connections")
        except Exception as e:
            print(f"Error during graph sync: {e}")

        finally:
            # Always clear sync flag
            self._syncing = False

    # Node Management
    def add_node_visual(self, node: BaseNode, position: Tuple[float, float] = (100, 100)) -> bool:
        """Add a visual representation of a node to the canvas."""
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
            
    
    def remove_node_visual(self, node_id: str) -> bool:
        """Remove a node's visual representation."""
        if node_id not in self.node_panels:
            return False
            
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
        
    def add_connection_visual(self, edge: Edge) -> bool:
        """Add a visual connection between two nodes."""
        print(f"🔗 Python: Adding connection visual for {edge.output_node_id}:{edge.outlet_pin_id} -> {edge.input_node_id}:{edge.inlet_pin_id}")
        edge_key = self._get_edge_key(edge)
        
        # Create pin IDs in the expected format
        from_pin_id = f"{edge.output_node_id}:{edge.outlet_pin_id}"
        to_pin_id = f"{edge.input_node_id}:{edge.inlet_pin_id}"
        connection_id = edge_key  # Use edge key as connection ID
        
        self.canvas_vue.add_connection_visual(connection_id, from_pin_id, to_pin_id)
        self.connection_paths[edge_key] = connection_id
        print(f"🔗 Python: Created connection via Vue component with ID: {connection_id}")
        return True
   
    def remove_connection_visual(self, edge_key: str) -> bool:
        """Remove a connection's visual representation."""
        if edge_key not in self.connection_paths:
            return False
            
        path_id = self.connection_paths[edge_key]
        
        # Use Vue component to remove connection visual
        success = self.canvas_vue.remove_connection_visual(path_id)
        if success:
            del self.connection_paths[edge_key]
            return True
        
        return False
   
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
        try:
            self.canvas_vue.select_node(node_id, multi_select)
        except (AttributeError, RuntimeError) as e:
            print(f"Warning: Could not update visual selection for node {node_id}: {e}")
    
    def deselect_node(self, node_id: str):
        """Deselect a node."""
        self.selected_nodes.discard(node_id)
        
        # Update visual selection in Vue component
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
        if edge_key in self.connection_paths:
            try:
                path_id = self.connection_paths[edge_key]
                self.canvas_vue.select_connection(path_id, multi_select)
                print(f"🎯 Selected connection: {edge_key}")
            except (AttributeError, RuntimeError) as e:
                print(f"Warning: Could not update visual selection for connection {edge_key}: {e}")
    
    def deselect_connection(self, edge_key: str):
        """Deselect a connection."""
        self.selected_connections.discard(edge_key)
        
        # Update visual selection in Vue component
        if edge_key in self.connection_paths:
            try:
                path_id = self.connection_paths[edge_key]
                self.canvas_vue.deselect_connection(path_id)
                print(f"🎯 Deselected connection: {edge_key}")
            except (AttributeError, RuntimeError) as e:
                print(f"Warning: Could not update visual deselection for connection {edge_key}: {e}")
        
    def clear_selection(self):
        """Clear all selections."""
        self.selected_nodes.clear()
        self.selected_connections.clear()
        
        # Update visual selection in Vue component
        try:
            self.canvas_vue.clear_selection()
            print("🎯 Cleared all selections")
        except (AttributeError, RuntimeError) as e:
            print(f"Warning: Could not clear visual selection: {e}")
        
    
    def get_selected_nodes(self) -> Set[str]:
        """Get currently selected nodes."""
        return self.selected_nodes.copy()
    
    def get_selected_connections(self) -> Set[str]:
        """Get currently selected connections."""
        return self.selected_connections.copy()
                      
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

    # Connection Management
    def _get_edge_key(self, edge: Edge) -> str:
        """Generate a unique key for an edge using Format 2."""
        return generate_connection_id(
            edge.output_node_id, 
            edge.outlet_pin_id, 
            edge.input_node_id, 
            edge.inlet_pin_id
        )

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
