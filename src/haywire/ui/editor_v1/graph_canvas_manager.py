"""
GraphCanvasManager - Enhanced with consolidated event system

CONSOLIDATED VERSION: Simplified drag, selection, and removal events.
"""

import traceback
from typing import Dict, List, Optional, Tuple, Callable, Set
from nicegui import ui, events
from dataclasses import dataclass

from haywire.core.graph.graph import HaywireGraph, Edge, EdgeType
from haywire.core.node.node import BaseNode
from haywire.ui.utils import generate_pin_id, parse_pin_id, generate_connection_id, parse_connection_id
from haywire.undo.actions.graph_actions import ChangeSelectionAction, SelectionState, MoveNodeAction, AddEdgeAction, RemoveNodeAction, RemoveEdgeAction, AddNodeAction
from haywire.ui.ui_node import UINode
from haywire.ui.pan_zoom.zoom_pan_vue import ZoomPanContainer

from .graph_canvas_vue import GraphCanvasVue
from .popup_context_menu import PopupContextMenu
from .event_definitions import *
from .event_handlers import handles_event
from .editor import Editor


class GraphCanvasManager:
    """
    Hybrid graph canvas manager with consolidated event system.
    
    Features consolidated events:
    - userDragStart/Update/End (replaces node drag and selection drag events)
    - userRemove (replaces node and connection removal events)
    - Unified selection system
    """

    def __init__(
        self, 
        editor: Editor,
        node_render_factory,
        available_nodes: Optional[List[str]] = None,
        session_id: Optional[str] = None,
    ):
        self.editor = editor
        self.node_render_factory = node_render_factory
        self.available_nodes = available_nodes or []
        self.session_id = session_id or "default"
        
        # Access graph for read operations
        self.graph = editor.graph
        
        # Register for simple graph change notifications
        self.editor.add_change_callback(self._on_graph_changed)
                
        # Visual state
        self.node_panels: Dict[str, Dict] = {}  # node_id -> {ui_node, container, position}
        self.connection_paths: Dict[str, Edge] = {}  # connection_id -> Edge object
        self.selected_nodes: Set[str] = set()
        self.selected_connections: Set[str] = set()
        
        # Vue component for canvas interactions
        self.canvas_vue: Optional[GraphCanvasVue] = None
        self.context_menu: Optional[PopupContextMenu] = None
        self.zoom_container: Optional[ZoomPanContainer] = None
        
        # Enhanced event handling system for UI events
        self._event_handlers: Dict[str, Callable] = {}
        self._auto_register_event_handlers()
        
        # Drag state tracking for consolidated events
        self._drag_state = {
            'is_dragging': False,
            'dragged_elements': [],  # [{'type': 'node', 'id': 'node1'}, ...]
            'initial_positions': {},  # element_id -> {'x': x, 'y': y}
        }
        
        self._setup_canvas()
    
    def _on_graph_changed(self):
        """Simple callback when anything changes in the graph."""
        print(f"🔄 GraphCanvasManager[{self.session_id[:8]}]: Graph changed, syncing visuals")
        self.sync_with_graph()
    
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
        print("🔧 Setting up GraphCanvasManager with consolidated events")
        
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
                on_emit_event=self._handle_canvas_event
            )

    def _handle_canvas_event(self, event: BaseGraphEvent):
        """Unified canvas event router using auto-registered handlers"""
        event_type = event.event_type
        handler = self._event_handlers.get(event_type)
        
        if handler:
            print(f"🔧 Calling handler for {event_type}: {handler.__name__}")
            try:
                handler(event)
            except Exception as e:
                print(f"❌ Error calling handler for {event_type}: {e}")
                ui.notify(f"Error while processing {event.description}: {e}", type='negative')
                traceback.print_exc()
        else:
            print(f"No handler found for event type: {event_type}")
    
    # =============================================================================
    # CONSOLIDATED EVENT HANDLERS
    # =============================================================================
    
    @handles_event(UserDragStartEvent)
    def process_drag_start(self, event: UserDragStartEvent):
        """Handle unified drag start for nodes"""        
        # Add fence for undo grouping
        self.editor.add_fence()
        
    @handles_event(UserDragUpdateEvent)
    def process_drag_update(self, event: UserDragUpdateEvent):
        """Handle unified drag updates for nodes"""
        print(f"Dragging {len(event.nodes)} nodes by ({event.deltaX}, {event.deltaY})")
       
        # Update positions for dragged nodes
        for node_id in event.nodes:
            # Update stored position when user drags
            if node_id in self.node_panels:
                
                position = self.node_panels[node_id]['position']
                posX = position[0] + event.deltaX
                posY = position[1] + event.deltaY
                self.node_panels[node_id]['position'] = (posX, posY)

                print(f"Node {node_id} dragging from ({position[0]}, {position[1]}) to ({posX}, {posY})")
            
                # Update node position via editor
                self.editor.move_node(node_id, posX, posY)
    
    @handles_event(UserDragEndEvent)
    def process_drag_end(self, event: UserDragEndEvent):
        """Handle unified drag end for nodes"""
        self.editor.add_fence()
        
    
    @handles_event(UserRemoveEvent)
    def process_element_removal(self, event: UserRemoveEvent):
        """Handle unified element removal"""
        total_elements = len(event.nodes) + len(event.connections)
        print(f"🗑️ Removing {total_elements} elements: {len(event.nodes)} nodes, {len(event.connections)} connections")
        
        success_count = 0
        
        # Remove nodes
        for node_id in event.nodes:
            if node_id in self.graph.nodes:
                if self.editor.delete_node(node_id):
                    success_count += 1
                    print(f"✅ Deleted node: {node_id}")
                else:
                    print(f"❌ Failed to delete node: {node_id}")
        
        # Remove connections
        for connection_id in event.connections:
            if connection_id in self.connection_paths:
                edge_to_remove = self.connection_paths[connection_id]
                if self.editor.delete_connection_by_edge(edge_to_remove):
                    success_count += 1
                    print(f"✅ Deleted connection: {connection_id}")
                else:
                    print(f"❌ Failed to delete connection: {connection_id}")
        
        if success_count > 0:
            ui.notify(f"Deleted {success_count} element(s)", type='positive')
        else:
            ui.notify("No elements could be deleted", type='warning')
    
                            
    @handles_event(ConnectionCreatedEvent)
    def process_connection_creation(self, event: ConnectionCreatedEvent):
        """Handle connection creation"""
        print(f"Creating connection: {event.outputNodeId}:{event.outletPinId} -> {event.inputNodeId}:{event.inletPinId}")

        if self.editor.create_connection(
            event.outputNodeId,
            event.outletPinId,
            event.inputNodeId,
            event.inletPinId
        ):
            ui.notify(f"Connection created")
        else:
            ui.notify(f"Failed to create connection", type='negative')

    @handles_event(ConnectionClickedEvent)
    def process_connection_click(self, event: ConnectionClickedEvent):
        """Handle connection click events"""
        try:
            print(f"Connection clicked: {event.connectionId}")
        except Exception as e:
            print(f"Connection click handling failed: {e}")

    @handles_event(SelectionChangedEvent)
    def process_selection_change(self, event: SelectionChangedEvent):
        """Handle selection changes"""
        print(f"Selection changed: nodes={event.selectedNodes}, connections={event.selectedConnections}")
        
        # Create new selection state
        selected_nodes_set = set(event.selectedNodes)
        selected_connections_set = set(event.selectedConnections)
        
        # Convert connection IDs to edge tuples for SelectionState format
        selected_edges = set()
        for connection_id in selected_connections_set:
            try:
                components = parse_connection_id(connection_id)
                selected_edges.add((components.outlet_node_id, components.outlet_pin_id, 
                                  components.inlet_node_id, components.inlet_pin_id))
            except (ValueError, AttributeError):
                continue
        
        # Use Editor to set selection
        self.editor.set_selection(selected_nodes_set, selected_edges)
        
        # Update local state for fast access
        self.selected_nodes = selected_nodes_set
        self.selected_connections = selected_connections_set
    
    @handles_event(ContextMenuCanvasEvent, ContextMenuNodeEvent, ContextMenuConnectionEvent, ContextMenuSelectedEvent)
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
        
        elif isinstance(event, ContextMenuSelectedEvent):
            print(f"Selected context menu at ({event.screenX}, {event.screenY}) for {len(event.selectedNodes)} nodes, {len(event.selectedConnections)} connections")
            if self.context_menu:
                self.context_menu.show_selected_menu(event.screenX, event.screenY, event.selectedNodes, event.selectedConnections)
    
    @handles_event(NodeCreateRequestEvent)
    def process_node_creation_request(self, event: NodeCreateRequestEvent):
        """Handle node creation requests from context menu or other sources."""
        print(f"📝 Processing node creation request: {event.nodeType} at ({event.position['x']}, {event.position['y']})")
        
        try:
            node = self.editor.create_node(
                event.nodeType,
                (event.position['x'], event.position['y'])
            )
            
            if node:
                print(f"✅ Created node {node.node_id} at ({event.position['x']}, {event.position['y']})")
                ui.notify(f"Created {event.nodeType} node", type='positive')
            else:
                ui.notify(f"Failed to create node of type: {event.nodeType}", type='negative')
                
        except Exception as e:
            print(f"Error creating node: {e}")
            ui.notify(f"Error creating node: {e}", type='negative')

    # =============================================================================
    # SYNC UI with GRAPH STATE (unchanged from original)
    # =============================================================================

    def sync_with_graph(self):
        """Synchronize visual representation with the graph state."""
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
                
                if new_position != old_position:
                    print(f"Updating node {node_id} position: {old_position} -> {new_position}")
                    self.update_node_position(node_id, new_position)
            
            # Sync connections
            current_connection_ids = set(self.connection_paths.keys())
            graph_connection_ids = set()
            
            for edge in self.graph.edges:
                connection_id = generate_connection_id(
                    edge.output_node_id, edge.outlet_pin_id,
                    edge.input_node_id, edge.inlet_pin_id
                )
                graph_connection_ids.add(connection_id)
                
                if connection_id not in current_connection_ids:
                    print(f"🔄 Adding new connection: {connection_id}")
                    self.add_connection_visual(edge)
            
            connections_to_remove = current_connection_ids - graph_connection_ids
            for connection_id in connections_to_remove:
                print(f"🔄 Removing old connection: {connection_id}")
                self.remove_connection_visual(connection_id)
            
            print(f"🔄 Incremental connection sync: {len(graph_connection_ids)} total connections")
            
            # Sync selection state from graph to UI
            graph_selected_nodes, graph_selected_connections = self.graph.get_selection_state()
            
            self.clear_selection()
            
            for node_id in graph_selected_nodes:
                self.select_node(node_id, multi_select=True)
            
            for connection_id in graph_selected_connections:
                self.select_connection(connection_id, multi_select=True)

            self.canvas_vue.update() 
                
            print(f"🔄 Selection synced from graph: {len(graph_selected_nodes)} nodes, {len(graph_selected_connections)} connections")
        except Exception as e:
            print(f"Error during graph sync: {e}")
            traceback.print_exc()
    
    def cleanup(self):
        """Cleanup resources and unregister from Editor."""
        if self.editor:
            self.editor.remove_change_callback(self._on_graph_changed)
            print(f"🧹 GraphCanvasManager[{self.session_id[:8]}]: Cleanup completed")

    # =============================================================================
    # NODE MANAGEMENT (unchanged from original)
    # =============================================================================

    def add_node_visual(self, node: BaseNode, position: Tuple[float, float] = (100, 100)) -> bool:
        """Add a visual representation of a node to the canvas."""
        x, y = position
        print(f"Adding node visual for {node.node_id} at position ({x}, {y})")
        
        with self.canvas_vue:
            with ui.element('div').classes(
                    'absolute'
                ).style(
                    f'left: {x}px; '
                    f'top: {y}px; '
                    f'z-index: 100; '
                    f'transform-origin: top-left; cursor: move;'
                ).props(
                    f'id="{node.node_id}" '
                    f'data-node-id="{node.node_id}" '
                ) as container:    

                print(f"Created container for node {node.node_id}")
                
                ui_node = UINode(node, self.node_render_factory, container)
                ui_node.render()
                print(f"Rendered UINode for {node.node_id}")
                
                self.node_panels[node.node_id] = {
                    'ui_node': ui_node,
                    'container': container,
                    'position': position
                }
                
                sync_event = SyncNodeObserverAddEvent(nodeId=node.node_id)
                self.canvas_vue.emit_sync_event(sync_event)

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
                connection_id = generate_connection_id(
                    edge.output_node_id, edge.outlet_pin_id,
                    edge.input_node_id, edge.inlet_pin_id
                )
                edges_to_remove.append(connection_id)
        
        for connection_id in edges_to_remove:
            self.remove_connection_visual(connection_id)
        
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
        
        sync_event = SyncNodeObserverRemoveEvent(nodeId=node_id)
        self.canvas_vue.emit_sync_event(sync_event)
        
        return True
                
    def update_node_position(self, node_id: str, position: Tuple[float, float]):
        """Update a node's visual position."""
        if node_id not in self.node_panels:
            return
            
        x, y = position
        container = self.node_panels[node_id]['container']
        
        container.style(f'left: {x}px; top: {y}px; z-index: 100;')
        container.update()
        
        self.node_panels[node_id]['position'] = position
        
        sync_event = SyncNodePositionEvent(
            nodeId=node_id,
            position={'x': x, 'y': y}
        )
        self.canvas_vue.emit_sync_event(sync_event)
        
    def add_connection_visual(self, edge: Edge) -> bool:
        """Add a visual connection between two nodes."""
        print(f"🔗 Python: Adding connection visual for {edge.output_node_id}:{edge.outlet_pin_id} -> {edge.input_node_id}:{edge.inlet_pin_id}")
        connection_id = generate_connection_id(
            edge.output_node_id, edge.outlet_pin_id,
            edge.input_node_id, edge.inlet_pin_id
        )
        
        sync_event = SyncConnectionAdditionEvent(
            connectionId=connection_id,
            outputNodeId=edge.output_node_id,
            outletPinId=edge.outlet_pin_id,
            inputNodeId=edge.input_node_id,
            inletPinId=edge.inlet_pin_id,
            isValid=edge.is_valid
        )        
        self.canvas_vue.emit_sync_event(sync_event)

        self.connection_paths[connection_id] = edge
        print(f"🔗 Python: Created connection via direct sync event with ID: {connection_id}")
        return True
   
    def remove_connection_visual(self, connection_id: str) -> bool:
        """Remove a connection's visual representation."""
        if connection_id not in self.connection_paths:
            return False
            
        edge = self.connection_paths[connection_id]
        
        sync_event = SyncConnectionRemovalEvent(connectionId=connection_id)
        self.canvas_vue.emit_sync_event(sync_event)

        del self.connection_paths[connection_id]
        return True
   
    def clear_all_visuals(self):
        """Clear all visual representations."""
        sync_event = SyncCanvasClearEvent()        
        self.canvas_vue.emit_sync_event(sync_event)
        
        # Clear local state
        self.node_panels.clear()
        self.connection_paths.clear()
        self.selected_nodes.clear()
        self.selected_connections.clear()
    
    # =============================================================================
    # SELECTION MANAGEMENT (unchanged from original)
    # =============================================================================
    
    def select_node(self, node_id: str, multi_select: bool = False):
        """Select a node."""
        if not multi_select:
            self.selected_nodes.clear()
        
        self.selected_nodes.add(node_id)
        
        sync_event = SyncNodeSelectionEvent(
            nodeId=node_id,
            selected=True,
            multiSelect=multi_select
        )
        self.canvas_vue.emit_sync_event(sync_event)
    
    def deselect_node(self, node_id: str):
        """Deselect a node."""
        self.selected_nodes.discard(node_id)
        
        sync_event = SyncNodeSelectionEvent(
            nodeId=node_id,
            selected=False,
            multiSelect=False
        )
        self.canvas_vue.emit_sync_event(sync_event)
    
    def select_connection(self, connection_id: str, multi_select: bool = False):
        """Select a connection."""
        if not multi_select:
            self.selected_connections.clear()
        
        self.selected_connections.add(connection_id)
        
        if connection_id in self.connection_paths:
            sync_event = SyncConnectionSelectionEvent(
                connectionId=connection_id,
                selected=True,
                multiSelect=multi_select
            )
            self.canvas_vue.emit_sync_event(sync_event)
            print(f"🎯 Selected connection: {connection_id}")
    
    def deselect_connection(self, connection_id: str):
        """Deselect a connection."""
        self.selected_connections.discard(connection_id)
        
        if connection_id in self.connection_paths:
            sync_event = SyncConnectionSelectionEvent(
                connectionId=connection_id,
                selected=False,
                multiSelect=False
            )
            self.canvas_vue.emit_sync_event(sync_event)
            print(f"🎯 Deselected connection: {connection_id}")
        
    def clear_selection(self):
        """Clear all selections."""
        self.selected_nodes.clear()
        self.selected_connections.clear()
        
        sync_event = SyncClearAllSelectionsEvent()
        self.canvas_vue.emit_sync_event(sync_event)
        print("🎯 Cleared all selections")
        
    def get_selected_nodes(self) -> Set[str]:
        """Get currently selected nodes."""
        return self.selected_nodes.copy()
    
    def get_selected_connections(self) -> Set[str]:
        """Get currently selected connections."""
        return self.selected_connections.copy()
                      
    # =============================================================================
    # ZOOM CONTROL AND OBSERVERS (unchanged from original)
    # =============================================================================
    
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

    def add_node_observer(self, node_id: str):
        """Add observers for a node."""
        sync_event = SyncNodeObserverAddEvent(nodeId=node_id)
        self.canvas_vue.emit_sync_event(sync_event)

    def remove_node_observer(self, node_id: str):
        """Remove observers for a node."""
        sync_event = SyncNodeObserverRemoveEvent(nodeId=node_id)
        self.canvas_vue.emit_sync_event(sync_event)

    def update_connections_for_node(self, node_id: str):
        """Update connections for a specific node."""
        sync_event = SyncConnectionsUpdateEvent(nodeId=node_id)
        self.canvas_vue.emit_sync_event(sync_event)

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