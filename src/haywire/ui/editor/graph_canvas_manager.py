"""
GraphCanvasManager - Enhanced with consolidated event system

CONSOLIDATED VERSION: Simplified drag, selection, and removal events.
"""

import traceback
import time
import uuid
from typing import Dict, List, Optional, Tuple, Callable, Set
from nicegui import ui, events
from dataclasses import dataclass

from haywire.core.graph.base import BaseGraph, Edge, EdgeType
from haywire.core.node.base import BaseNode
from haywire.ui.utils import generate_pin_uuid, parse_pin_uuid, generate_connection_uuid, parse_connection_uuid
from haywire.ui.ui_node import NiceUINode
from haywire.ui.pan_zoom.zoom_pan_vue import ZoomPanContainer

from .graph_canvas_vue import GraphCanvasVue
from .popup_context_menu import PopupContextMenu
from .event_definitions import *
from .event_handlers import handles_event
from .editor import Editor
from ...undo.actions.graph_actions import ClipboardData, PasteClipboardAction


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
        session_id: Optional[str] = None,
    ):
        self.editor = editor
        self.node_render_factory = node_render_factory
        self.session_id = session_id or "default"
        
        # Access graph for read operations
        self.graph = editor.graph
        
        # Register for simple graph change notifications
        self.editor.add_change_callback(self._on_graph_changed)
        
        # Register for NodeWrapper change notifications
        # Note: We keep wrapper callback setup to ensure wrappers are properly initialized
        # UINode now handles its own hot reload, but we still setup the callbacks for new nodes
        self._setup_wrapper_callbacks()
                
        # Visual state
        self.node_panels: Dict[str, Dict] = {}  # node_id -> {ui_node, container, position}
        self.connection_paths: Dict[str, Edge] = {}  # connection_uuid -> Edge object
        self.selected_nodes: Set[str] = set()
        self.selected_connections: Set[str] = set()
        
        # Vue component for canvas interactions
        self.canvas_vue: Optional[GraphCanvasVue] = None
        self.context_menu: Optional[PopupContextMenu] = None
        self.zoom_container: Optional[ZoomPanContainer] = None
        
        # Session clipboard for copy/paste functionality
        self.clipboard: Optional[ClipboardData] = None
        
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
        
        # Update wrapper callbacks for any new wrappers
        self._setup_wrapper_callbacks()
    
    def _setup_wrapper_callbacks(self):
        """
        Setup wrapper callbacks for new wrappers.
        
        Note: UINode now handles hot reload directly by subscribing to wrapper callbacks.
        This method just ensures wrappers have their internal callbacks properly set up.
        The actual hot reload visual updates are handled by UINode._on_wrapper_changed().
        """
        for wrapper in self.graph.node_wrappers.values():
            # Wrappers handle their own internal state management
            # UINode subscribes directly when created in add_node_visual()
            pass
    
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
                editor=self.editor,
                on_emit_event=self._handle_canvas_event,
                clipboard_checker=self._has_clipboard_content
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
    #  EVENT HANDLERS
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
               
        self.editor.move_nodes(event.nodes, event.deltaX, event.deltaY)
    
    @handles_event(UserDragEndEvent)
    def process_drag_end(self, event: UserDragEndEvent):
        """Handle unified drag end for nodes"""
        self.editor.add_fence()
        
    
    @handles_event(UserRemoveEvent)
    def process_element_removal(self, event: UserRemoveEvent):
        """Handle unified element removal"""
        total_elements = len(event.nodes) + len(event.connections)
        print(f"🗑️ Removing {total_elements} elements: {len(event.nodes)} nodes, {len(event.connections)} connections")
        
        # Use the new unified removal method
        if self.editor.remove_elements(event.nodes, event.connections):
            ui.notify(f"Deleted {total_elements} element(s)", type='positive')
        else:
            ui.notify("Failed to delete elements", type='warning')
    
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
            print(f"Connection clicked: {event.connectionUUID}")
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
        for connection_uuid in selected_connections_set:
            try:
                components = parse_connection_uuid(connection_uuid)
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
            print(f"Connection context menu for {event.connectionUUID} at ({event.screenX}, {event.screenY})")
            if self.context_menu:
                self.context_menu.show_connection_menu(event.screenX, event.screenY, event.connectionUUID)
        
        elif isinstance(event, ContextMenuSelectedEvent):
            print(f"Selected context menu at ({event.screenX}, {event.screenY}) for {len(event.selectedNodes)} nodes, {len(event.selectedConnections)} connections")
            if self.context_menu:
                self.context_menu.show_selected_menu(event.screenX, event.screenY, event.selectedNodes, event.selectedConnections)
    
    @handles_event(NodeCreateRequestEvent)
    def process_node_creation_request(self, event: NodeCreateRequestEvent):
        """Handle node creation requests from context menu or other sources."""
        print(f"📝 Processing node creation request: {event.registryKey} at ({event.position['x']}, {event.position['y']})")
        
        try:
            wrapper = self.editor.create_wrapper(
                event.registryKey,
                (event.position['x'], event.position['y'])
            )
            
            if wrapper:
                print(f"✅ Created node {wrapper.node_id} at ({event.position['x']}, {event.position['y']})")
                ui.notify(f"Created {event.registryKey} node", type='positive')
            else:
                ui.notify(f"Failed to create node of type: {event.registryKey}", type='negative')
                
        except Exception as e:
            print(f"Error creating node: {e}")
            ui.notify(f"Error creating node: {e}", type='negative')

    @handles_event(UserCopySelectedEvent)
    def process_copy_selection(self, event: UserCopySelectedEvent):
        """Handle copying selected elements to clipboard."""
        print(f"📋 Copying {len(event.selectedNodes)} nodes and {len(event.selectedConnections)} connections")
        
        try:
            # Calculate bounding box for positioning
            bounding_box = self._calculate_selection_bounds(event.selectedNodes)
 
            # Store in session clipboard
            self.clipboard = ClipboardData(
                nodes=event.selectedNodes,
                edges=event.selectedConnections,
                original_to_new_ids={},  # Not needed for copy
                bounding_box=bounding_box,
                timestamp=time.time(),
                source_session_id=self.session_id
            )
                        
        except Exception as e:
            print(f"❌ Error during copy operation: {e}")
            ui.notify(f"Copy failed: {e}", type='negative')
            traceback.print_exc()
    
    @handles_event(UserPasteClipboardEvent)
    def process_paste_clipboard(self, event: UserPasteClipboardEvent):
        """Handle pasting clipboard contents."""
        if not self.clipboard:
            print("❌ No clipboard content to paste")
            ui.notify("Nothing to paste", type='warning')
            return
            
        print(f"📄 Pasting {len(self.clipboard.nodes)} nodes and {len(self.clipboard.edges)} connections at ({event.canvasX}, {event.canvasY})")

        """

        try:
            # Filter connections - only between selected nodes
            valid_edges = []
            for conn_uuid in self.clipboard.edges:
                edge = self.graph.get_edge(conn_uuid)
                if edge and edge.output_node_id in self.clipboard.edges and edge.input_node_id in event.selectedNodes:
                    valid_edges.append((conn_uuid, edge))
                        
            # Create new node instances with new IDs
            new_nodes = {}
            id_mapping = {}
            
            for original_node_id in self.clipboard.nodes:
                original_node = self.graph.get_node(original_node_id)
                if not original_node:
                    continue
               
                # Generate new ID and create new instance
                new_node_id = f"copy_{uuid.uuid4().hex[:8]}_{original_node_id}"

                new_node_wrapper = self.graph.create_node_wrapper(registry_key=original_node.identity.registry_key)
                new_node_wrapper.initialize()


                
                # Clone inlet/outlet data and configuration
                self._clone_node_data(original_node, new_node)
                
                # Copy position
                new_node.ui_state.posX = original_node.ui_state.posX
                new_node.ui_state.posY = original_node.ui_state.posY
                
                new_nodes[new_node_id] = new_node
                id_mapping[original_node_id] = new_node_id
            
            # Create new edges with mapped node IDs
            new_edges = {}
            for conn_uuid, edge in valid_edges:
                if edge.output_node_id in id_mapping and edge.input_node_id in id_mapping:
                    new_conn_uuid = generate_connection_uuid(
                        id_mapping[edge.output_node_id], edge.outlet_pin_id,
                        id_mapping[edge.input_node_id], edge.inlet_pin_id
                    )
                    
                    new_edge = Edge(
                        edge_type=edge.edge_type,
                        output_node_id=id_mapping[edge.output_node_id],
                        outlet_pin_id=edge.outlet_pin_id,
                        input_node_id=id_mapping[edge.input_node_id],
                        inlet_pin_id=edge.inlet_pin_id,
                        outlet_pin_data_type=edge.outlet_pin_data_type,
                        inlet_pin_data_type=edge.inlet_pin_data_type,
                        is_valid=edge.is_valid
                    )
                    
                    new_edges[new_conn_uuid] = new_edge
            
            # Store in session clipboard
            tmp_clipboard = ClipboardData(
                nodes=new_nodes,
                edges=new_edges,
                original_to_new_ids=id_mapping,
                bounding_box=self.clipboard.bounding_box,
                timestamp=time.time(),
                source_session_id=self.session_id
            )
            
            # Create and execute paste action
            paste_action = PasteClipboardAction(
                graph=self.graph,
                clipboard_data=tmp_clipboard,
                paste_x=event.canvasX,
                paste_y=event.canvasY
            )
            
            # Execute through editor's history manager for undo/redo support
            self.editor.history_manager.add_action(paste_action)
            
            # Notify change callbacks
            self.editor._notify_change("paste_clipboard")
            
            print("✅ Paste operation completed successfully")
            ui.notify(f"Pasted {len(self.clipboard.nodes)} nodes", type='positive')
                        
        except Exception as e:
            print(f"❌ Error during paste operation: {e}")
            ui.notify(f"Paste failed: {e}", type='negative')
            traceback.print_exc()

        """
            
    # =============================================================================
    # SYNC UI with GRAPH STATE (unchanged from original)
    # =============================================================================

    def sync_with_graph(self):
        """Synchronize visual representation with the graph state."""
        try:
            # Sync nodes (using node_wrappers)
            graph_node_ids = set(self.graph.node_wrappers.keys())
            visual_node_ids = set(self.node_panels.keys())
            
            # Add missing nodes
            for node_id in graph_node_ids - visual_node_ids:
                wrapper = self.graph.node_wrappers[node_id]
                node = wrapper.node  # Get node instance from wrapper
                position = (
                    node.ui_state.posX,
                    node.ui_state.posY
                )
                self.add_node_visual(node, position)
            
            # Remove extra nodes
            for node_id in visual_node_ids - graph_node_ids:
                self.remove_node_visual(node_id)
                
            # Update positions of existing nodes
            for node_id in graph_node_ids.intersection(visual_node_ids):
                wrapper = self.graph.node_wrappers[node_id]
                node = wrapper.node  # Get node instance from wrapper
                new_position = (
                    node.ui_state.posX,
                    node.ui_state.posY
                )
                old_position = self.node_panels[node_id]['position']
                
                if new_position != old_position:
                    print(f"Updating node {node_id} position: {old_position} -> {new_position}")
                    self.update_node_position(node_id, new_position)
            
            # Sync connections
            current_connection_uuids = set(self.connection_paths.keys())
            graph_connection_uuids = set()
            
            for connection_uuid, edge in self.graph.edges.items():
                graph_connection_uuids.add(connection_uuid)
                
                if connection_uuid not in current_connection_uuids:
                    print(f"🔄 Adding new connection: {connection_uuid}")
                    self.add_connection_visual(edge)
            
            connections_to_remove = current_connection_uuids - graph_connection_uuids
            for connection_uuid in connections_to_remove:
                print(f"🔄 Removing old connection: {connection_uuid}")
                self.remove_connection_visual(connection_uuid)
            
            print(f"🔄 Incremental connection sync: {len(graph_connection_uuids)} total connections")
            
            # Sync selection state from graph to UI
            graph_selected_nodes, graph_selected_connections = self.graph.get_selection_state()
            
            # Update selection state without emitting events until the end
            self.selected_nodes.clear()
            self.selected_connections.clear()
            
            self.selected_nodes.update(graph_selected_nodes)
            self.selected_connections.update(graph_selected_connections)
            
            # Emit single consolidated selection sync event
            self.sync_selections()

            self.canvas_vue.update() 
                
            print(f"🔄 Selection synced from graph: {len(graph_selected_nodes)} nodes, {len(graph_selected_connections)} connections")
        except Exception as e:
            print(f"Error during graph sync: {e}")
            traceback.print_exc()
    
    def add_node_visual(self, node: BaseNode, position: Tuple[float, float] = (100, 100)) -> bool:
        """Add a visual representation of a node to the canvas with hot reload support."""
        x, y = position
        node_id = node.node_id
        print(f"Adding node visual for {node_id} at position ({x}, {y})")
        
        # Get the wrapper for this node to enable hot reload support
        wrapper = self.graph.get_node_wrapper(node_id)
        if not wrapper:
            print(f"⚠️ ERROR: No wrapper found for node {node_id}, hot reload won't work")
        
        with self.canvas_vue:
            with ui.element('div').classes(
                    'absolute'
                ).style(
                    f'left: {x}px; '
                    f'top: {y}px; '
                    f'z-index: 100; '
                    f'transform-origin: top-left; cursor: move;'
                ).props(
                    f'id="{node_id}" '
                    f'data-node-id="{node_id}" '
                ) as container:    

                print(f"Created container for node {node_id}")
                
                # Create UINode with wrapper reference for hot reload support
                ui_node = NiceUINode(node, self.node_render_factory, container, wrapper)
                ui_node.render()
                print(f"Rendered UINode for {node_id}")
                
                self.node_panels[node_id] = {
                    'ui_node': ui_node,
                    'container': container,
                    'position': position
                }
                
                sync_event = SyncNodeObserverAddEvent(nodeId=node_id)
                self.canvas_vue.emit_sync_event(sync_event)

                print(f"Setup Vue observers for {node_id}")
        
        print(f"Successfully added node visual for {node_id}")
        return True
            
    def remove_node_visual(self, node_id: str) -> bool:
        """Remove a node's visual representation."""
        if node_id not in self.node_panels:
            return False
            
        # Remove all connected edges visually first
        edges_to_remove = []
        for connection_uuid, edge in self.graph.edges.items():
            if edge.input_node_id == node_id or edge.output_node_id == node_id:
                edges_to_remove.append(connection_uuid)
        
        for connection_uuid in edges_to_remove:
            self.remove_connection_visual(connection_uuid)
        
        # Remove node visual
        visual_data = self.node_panels[node_id]
        
        if 'ui_node' in visual_data:
            ui_node = visual_data['ui_node']
            # Call destroy() to properly cleanup and unsubscribe from callbacks
            ui_node.destroy()
        
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
        connection_uuid = generate_connection_uuid(
            edge.output_node_id, edge.outlet_pin_id,
            edge.input_node_id, edge.inlet_pin_id
        )
        
        sync_event = SyncConnectionAdditionEvent(
            connectionUUID=connection_uuid,
            outputNodeId=edge.output_node_id,
            outletPinId=edge.outlet_pin_id,
            inputNodeId=edge.input_node_id,
            inletPinId=edge.inlet_pin_id,
            isValid=edge.is_valid
        )        
        self.canvas_vue.emit_sync_event(sync_event)

        self.connection_paths[connection_uuid] = edge
        print(f"🔗 Python: Created connection via direct sync event with ID: {connection_uuid}")
        return True
   
    def remove_connection_visual(self, connection_uuid: str) -> bool:
        """Remove a connection's visual representation."""
        if connection_uuid not in self.connection_paths:
            return False
            
        edge = self.connection_paths[connection_uuid]
        
        sync_event = SyncConnectionRemovalEvent(connectionUUID=connection_uuid)
        self.canvas_vue.emit_sync_event(sync_event)

        del self.connection_paths[connection_uuid]
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
        
    def sync_selections(self):
        """Helper method to emit the consolidated selection sync event."""
        sync_event = SyncSelectionsEvent(
            nodes=list(self.selected_nodes),
            connections=list(self.selected_connections)
        )
        self.canvas_vue.emit_sync_event(sync_event)
    
    # =============================================================================
    # CLIPBOARD HELPER METHODS
    # =============================================================================
    
    def _has_clipboard_content(self) -> bool:
        """Check if clipboard has content available for pasting."""
        return self.clipboard is not None and len(self.clipboard.nodes) > 0
    
    def _calculate_selection_bounds(self, node_ids: List[str]) -> Dict[str, float]:
        """Calculate bounding box of selected nodes."""
        if not node_ids:
            return {'min_x': 0, 'min_y': 0, 'max_x': 0, 'max_y': 0}
        
        positions = []
        for node_id in node_ids:
            node = self.graph.get_node(node_id)
            if node:
                positions.append((node.ui_state.posX, node.ui_state.posY))
        
        if not positions:
            return {'min_x': 0, 'min_y': 0, 'max_x': 0, 'max_y': 0}
        
        min_x = min(pos[0] for pos in positions)
        min_y = min(pos[1] for pos in positions)
        max_x = max(pos[0] for pos in positions)
        max_y = max(pos[1] for pos in positions)
        
        return {
            'min_x': min_x,
            'min_y': min_y,
            'max_x': max_x,
            'max_y': max_y
        }
    
    def _clone_node_data(self, source_node: BaseNode, target_node: BaseNode):
        """Clone inlet/outlet data and configuration from source to target node."""
        try:
            # Copy behavior, ui_config, and metadata
            target_node.behavior = source_node.behavior
            target_node.ui_config = source_node.ui_config
            target_node.metadata = source_node.metadata
            
            # Deep copy inlets and outlets
            from copy import deepcopy
            
            for inlet_id, inlet in source_node.inlets.items():
                target_node.inlets[inlet_id] = deepcopy(inlet)
                
            for outlet_id, outlet in source_node.outlets.items():
                target_node.outlets[outlet_id] = deepcopy(outlet)
            
            # Reset cache
            target_node._cache_dirty = True
            
        except Exception as e:
            print(f"Warning: Could not fully clone node data: {e}")
            # Continue with basic copy - at minimum the node factory created the basic structure
                   