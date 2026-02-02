"""
GraphCanvasManager - Enhanced with consolidated event system

CONSOLIDATED VERSION: Simplified drag, selection, and removal events.
"""

import traceback
import time
import logging
from typing import Dict, List, Optional, Tuple, Callable, Set
from nicegui import ui

from haywire.core.edge.edge_wrapper import EdgeWrapper
from haywire.core.graph.editor import Editor
from haywire.core.graph.types import ChangeReason, ValidationResult
from haywire.core.node.base import BaseNode
from haywire.core.undo.actions.graph_actions import ClipboardData

from ..utils import parse_connection_uuid
from ..ui_node import UINode
from ..ui_edge import UIEdge
from ..pan_zoom.zoom_pan_vue import ZoomPanContainer
from .graph_canvas_vue import GraphCanvasVue
from .popup_context_menu import PopupContextMenu
from .event_definitions import (
    BaseGraphEvent,
    UserDragStartEvent,
    UserDragUpdateEvent,
    UserDragEndEvent,
    UserRemoveEvent,
    ConnectionCreatedEvent,
    ConnectionClickedEvent,
    SelectionChangedEvent,
    ContextMenuCanvasEvent,
    ContextMenuNodeEvent,
    ContextMenuConnectionEvent,
    ContextMenuSelectedEvent,
    NodeCreateRequestEvent,
    UserCopySelectedEvent,
    UserPasteClipboardEvent,
    SyncNodeObserverAddEvent,
    SyncNodeObserverRemoveEvent,
    SyncNodePositionEvent,
    SyncConnectionAdditionEvent,
    SyncConnectionRemovalEvent,
    SyncSelectionsEvent,
    SyncCanvasClearEvent,
    GRAPH_EVENT_REGISTRY,
    )
from .event_handlers import handles_event

logger = logging.getLogger(__name__)

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
        node_factory,
        session_id: Optional[str] = None,
    ):
        self.editor = editor
        self.node_render_factory = node_render_factory
        self.node_factory = node_factory
        self.session_id = session_id or "default"
        
        # Access graph for read operations
        self.graph = editor.graph

        # Subscribe to validation through graph's public API
        self.graph.subscribe_to_validation(self._on_validated)
       
        # Register for simple graph change notifications
        # self.editor.add_change_callback(self._graph_change_callback)
                       
        # Visual state
        self.node_panels: Dict[str, UINode] = {}  # node_id -> UINode
        self.connection_paths: Dict[str, UIEdge] = {}  # connection_uuid -> UIEdge object
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
        logger.info(f"🔧 GraphCanvasManager for {self.session_id} is setup")
             
    def _auto_register_event_handlers(self):
        """Automatically register event handlers using decorators"""
        logger.debug("🔧 Auto-registering event handlers...")
        
        for method_name in dir(self):
            method = getattr(self, method_name)
            if hasattr(method, '_handles_event_classes'):
                for event_class in method._handles_event_classes:
                    event_type = event_class.event_type
                    self._event_handlers[event_type] = method
        
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
            logger.warning(f"⚠️  Missing handlers for events: {missing_handlers}")
        else:
            logger.debug(f"✅ All {len(user_events)} user events have registered handlers")
    
    def _setup_canvas(self):
        """Setup canvas with enhanced event system."""
        
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
                node_factory=self.node_factory,
                on_emit_event=self._handle_canvas_event,
                clipboard_checker=self._has_clipboard_content
            )

    def _handle_canvas_event(self, event: BaseGraphEvent):
        """Unified canvas event router using auto-registered handlers"""
        event_type = event.event_type
        handler = self._event_handlers.get(event_type)
        
        if handler:
            logger.debug(f"🔧 Calling handler for {event_type}: {handler.__name__}")
            try:
                handler(event)
            except Exception as e:
                logger.error(f"❌ Error calling handler for {event_type}: {e}")
                ui.notify(f"Error while processing {event.description}: {e}", type='negative')
                traceback.print_exc()
        else:
            logger.warning(f"No handler found for event type: {event_type}")
    
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
        logger.debug(f"Dragging {len(event.nodes)} nodes by ({event.deltaX}, {event.deltaY})")
               
        self.editor.move_nodes(event.nodes, event.deltaX, event.deltaY)
    
    @handles_event(UserDragEndEvent)
    def process_drag_end(self, event: UserDragEndEvent):
        """Handle unified drag end for nodes"""
        self.editor.add_fence()
        
    
    @handles_event(UserRemoveEvent)
    def process_element_removal(self, event: UserRemoveEvent):
        """Handle unified element removal"""
        total_elements = len(event.nodes) + len(event.connections)
        logger.info(
            f"🗑️ Removing {total_elements} elements: "
            f"{len(event.nodes)} nodes, {len(event.connections)} connections"
        )
        
        # Use the new unified removal method
        if self.editor.remove_elements(event.nodes, event.connections):
            ui.notify(f"Deleted {total_elements} element(s)", type='positive')
        else:
            ui.notify("Failed to delete elements", type='warning')
    
    @handles_event(ConnectionCreatedEvent)
    def process_connection_creation(self, event: ConnectionCreatedEvent):
        """Handle connection creation"""
        logger.debug(
            f"Creating connection: {event.sourceNodeId}:{event.outletPinId} -> "
            f"{event.sinkNodeId}:{event.inletPinId}"
        )

        if self.editor.create_connection(
            event.sourceNodeId,
            event.outletPinId,
            event.sinkNodeId,
            event.inletPinId
        ):
            ui.notify("Connection created")
        else:
            ui.notify("Failed to create connection", type='negative')

    @handles_event(ConnectionClickedEvent)
    def process_connection_click(self, event: ConnectionClickedEvent):
        """Handle connection click events"""
        try:
            logger.debug(f"Connection clicked: {event.connectionUUID}")
        except Exception as e:
            logger.error(f"Connection click handling failed: {e}")

    @handles_event(SelectionChangedEvent)
    def process_selection_change(self, event: SelectionChangedEvent):
        """Handle selection changes"""
        logger.debug(
            f"Selection changed: nodes={event.selectedNodes}, "
            f"connections={event.selectedConnections}"
        )
        
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
    
    @handles_event(
        ContextMenuCanvasEvent,
        ContextMenuNodeEvent,
        ContextMenuConnectionEvent,
        ContextMenuSelectedEvent
    )
    def process_context_menu(self, event):
        """Handle context menu events"""
        if isinstance(event, ContextMenuCanvasEvent):
            logger.debug(f"Canvas context menu at ({event.screenX}, {event.screenY})")
            if self.context_menu:
                self.context_menu.show_canvas_menu(
                    event.screenX,
                    event.screenY,
                    event.canvasX,
                    event.canvasY
                )
            
        elif isinstance(event, ContextMenuNodeEvent):
            logger.debug(f"Node context menu for {event.nodeId} at ({event.screenX}, {event.screenY})")
            if self.context_menu:
                self.context_menu.show_node_menu(event.screenX, event.screenY, event.nodeId)
            
        elif isinstance(event, ContextMenuConnectionEvent):
            logger.debug(
                f"Connection context menu for {event.connectionUUID} "
                f"at ({event.screenX}, {event.screenY})"
            )
            if self.context_menu:
                # Get metrics directly and pass to menu
                ui_edge = self.connection_paths.get(event.connectionUUID)
                if ui_edge and ui_edge.wrapper:
                    self.context_menu.show_connection_menu(
                        event.screenX,
                        event.screenY,
                        event.connectionUUID,
                        ui_edge.wrapper.edge,
                        ui_edge.wrapper.get_state()
                    )
        
        elif isinstance(event, ContextMenuSelectedEvent):
            logger.debug(
                f"Selected context menu at ({event.screenX}, {event.screenY}) "
                f"for {len(event.selectedNodes)} nodes, "
                f"{len(event.selectedConnections)} connections"
            )
            if self.context_menu:
                self.context_menu.show_selected_menu(
                    event.screenX,
                    event.screenY,
                    event.selectedNodes,
                    event.selectedConnections
                )
    
    @handles_event(NodeCreateRequestEvent)
    def process_node_creation_request(self, event: NodeCreateRequestEvent):
        """Handle node creation requests from context menu or other sources."""
        logger.info(
            f"📝 Processing node creation request: {event.registryKey} "
            f"at ({event.position['x']}, {event.position['y']})"
        )
        
        try:
            wrapper = self.editor.create_wrapper(
                event.registryKey,
                (event.position['x'], event.position['y'])
            )
            
            if wrapper:
                logger.info(
                    f"✅ Created node {wrapper.node_id} "
                    f"at ({event.position['x']}, {event.position['y']})"
                )
                ui.notify(f"Created {event.registryKey} node", type='positive')
            else:
                ui.notify(f"Failed to create node of type: {event.registryKey}", type='negative')
                
        except Exception as e:
            logger.error(f"Error creating node: {e}")
            ui.notify(f"Error creating node: {e}", type='negative')

    @handles_event(UserCopySelectedEvent)
    def process_copy_selection(self, event: UserCopySelectedEvent):
        """Handle copying selected elements to clipboard."""
        logger.info(
            f"📋 Copying {len(event.selectedNodes)} nodes and "
            f"{len(event.selectedConnections)} connections"
        )
        
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
            logger.error(f"❌ Error during copy operation: {e}")
            ui.notify(f"Copy failed: {e}", type='negative')
            traceback.print_exc()
    
    @handles_event(UserPasteClipboardEvent)
    def process_paste_clipboard(self, event: UserPasteClipboardEvent):
        """Handle pasting clipboard contents."""
        if not self.clipboard:
            logger.warning("❌ No clipboard content to paste")
            ui.notify("Nothing to paste", type='warning')
            return
            
        logger.info(
            f"📄 Pasting {len(self.clipboard.nodes)} nodes and "
            f"{len(self.clipboard.edges)} connections "
            f"at ({event.canvasX}, {event.canvasY})"
        )

        """

        try:
            # Filter connections - only between selected nodes
            valid_edges = []
            for conn_uuid in self.clipboard.edges:
                edge = self.graph.get_edge(conn_uuid)
                if (edge and edge.output_node_id in self.clipboard.edges 
                    and edge.input_node_id in event.selectedNodes):
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

                new_node_wrapper = self.graph.create_node_wrapper(
                    registry_key=original_node.identity.registry_key
                )
                new_node_wrapper.initialize()


                
                # Clone inlet/outlet data and configuration
                self._clone_node_data(original_node, new_node)
                
                # Copy position
                new_node.ui.state.posX = original_node.ui.state.posX
                new_node.ui.state.posY = original_node.ui.state.posY
                
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
                        adapter_registry_keys=edge.adapter_registry_keys,
                        connection_uuid=new_conn_uuid
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
        
    def _on_validated(self, result: ValidationResult):
        """
        Handle validation results with flexible reason-based dispatch.
        """
        
        logger.info(
            f"🔄 Validation: {result.total_changes} changes in "
            f"{result.validation_time_ms:.2f}ms"
        )

        node_has_moved = False
        selection_changed = False

        # Process nodes by reason
        for node_id, reason in result.nodes.items():
            
            if reason == ChangeReason.NODE_ADDED:
                # Create new UI node
                wrapper = self.graph.get_node_wrapper(node_id)
                if wrapper and node_id not in self.node_panels:
                    self.add_node_visual(wrapper.node, (
                        wrapper.node.ui.state.posX,
                        wrapper.node.ui.state.posY
                    ))
                    logger.debug(f"  + Added node UI: {node_id}")
            
            elif reason == ChangeReason.NODE_REMOVED:
                # Remove UI node
                if node_id in self.node_panels:
                    self.remove_node_visual(node_id)
                    logger.debug(f"  - Removed node UI: {node_id}")
                        
            elif reason == ChangeReason.NODE_MOVED:
                # Cheap visual update - just position
                ui_node = self.node_panels.get(node_id)
                if ui_node:
                    wrapper = self.graph.get_node_wrapper(node_id)
                    if wrapper:
                        node = wrapper.node  # Get node instance from wrapper
                        new_position = (
                            node.ui.state.posX,
                            node.ui.state.posY
                        )  
                        self.update_node_position(node_id, new_position)
                        node_has_moved = True
                        logger.debug(f"  ↔ Moved node: {node_id}")
            
            elif reason in (ChangeReason.NODE_SELECTED, ChangeReason.NODE_DESELECTED):
                # Handle selection/deselection without clearing entire set
                is_selected = reason == ChangeReason.NODE_SELECTED
                if is_selected:
                    self.selected_nodes.add(node_id)
                else:
                    self.selected_nodes.discard(node_id)
                selection_changed = True
                logger.debug(f"  ✓ Selection changed: {node_id}")

            elif reason.requires_redraw():
                # Full redraw needed
                ui_node = self.node_panels.get(node_id)
                if ui_node:
                    ui_node.refresh(reason)  # Full re-render
                    logger.debug(f"  🔄 Redrawn node: {node_id} ({reason.value})")

        # Process edges by reason
        for edge_uuid, reason in result.edges.items():
            
            if reason == ChangeReason.EDGE_ADDED:
                # Create new UI edge
                wrapper = self.graph.get_edge_wrapper(edge_uuid)
                if wrapper and edge_uuid not in self.connection_paths:
                    self.add_connection_visual(wrapper)
                    logger.debug(f"  + Added edge UI: {edge_uuid}")
            
            elif reason == ChangeReason.EDGE_REMOVED:
                # Remove UI edge
                if edge_uuid in self.connection_paths:
                    self.remove_connection_visual(edge_uuid)
                    logger.debug(f"  - Removed edge UI: {edge_uuid}")
                        
            elif reason in (ChangeReason.EDGE_SELECTED, ChangeReason.EDGE_DESELECTED):
                # Handle selection/deselection without clearing entire set
                is_selected = reason == ChangeReason.EDGE_SELECTED
                if is_selected:
                    self.selected_connections.add(edge_uuid)
                else:
                    self.selected_connections.discard(edge_uuid)
                selection_changed = True
                logger.debug(f"  ✓ Selection changed: {edge_uuid}")

            elif reason.requires_redraw():
                # Full redraw needed
                ui_edge = self.connection_paths.get(edge_uuid)
                if ui_edge:
                    ui_edge.refresh(reason)  # Full re-render
                    logger.debug(f"  🔄 Redrawn edge: {edge_uuid} ({reason.value})")

        # Emit single consolidated sync events
        if node_has_moved:
            #self._update_connection_paths()
            pass

        if selection_changed:
            self.sync_selections()

        self.canvas_vue.update() 

    def sync_with_graph(self):
        """
        Synchronize visual representation with the graph state.
        
        This method creates a synthetic ValidationResult marking all existing
        graph elements as 'added', then processes it through the normal
        validation pipeline. This ensures initial sync uses the same code
        path as incremental updates.
        """
        logger.info(
            f"🔄 Initial sync: {len(self.graph.node_wrappers)} nodes, "
            f"{len(self.graph.edge_wrappers)} edges"
        )
        
        try:
            # Create synthetic validation result marking all elements as added
            synthetic_result = ValidationResult(
                nodes={
                    node_id: ChangeReason.NODE_ADDED 
                    for node_id in self.graph.node_wrappers.keys()
                },
                edges={
                    edge_uuid: ChangeReason.EDGE_ADDED 
                    for edge_uuid in self.graph.edge_wrappers.keys()
                },
                validation_time_ms=0.0
            )
                                    
            # Process through normal validation handler
            self._on_validated(synthetic_result)
            
            logger.info("✅ Initial sync completed via validation pipeline")
            
        except Exception as e:
            logger.error(f"❌ Error during initial sync: {e}")
            traceback.print_exc()
    
    def add_node_visual(self, node: BaseNode, position: Tuple[float, float] = (100, 100)) -> bool:
        """Add a visual representation of a node to the canvas with hot reload support."""
        x, y = position
        node_id = node.node_id
        logger.debug(f"Adding node visual for {node_id} at position ({x}, {y})")
        
        # Get the wrapper for this node to enable hot reload support
        wrapper = self.graph.get_node_wrapper(node_id)
        if not wrapper:
            logger.warning(f"⚠️ ERROR: No wrapper found for node {node_id}, hot reload won't work")
        
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

                logger.debug(f"Created container for node {node_id}")
                
                # Create UINode with wrapper reference for hot reload support
                ui_node = UINode(container, wrapper, self.node_render_factory)
                # Register sync event emitter for hot reload updates after 
                # the refresh() call. we need to wait until the UI is rendered.
                ui_node.register_sync_event_emitter(self.canvas_vue.emit_sync_event)
                ui_node.refresh(ChangeReason.NODE_ADDED)
                
                logger.debug(f"Rendered UINode for {node_id}")
                
                ui_node.position = position
                self.node_panels[node_id] = ui_node
                
                sync_event = SyncNodeObserverAddEvent(nodeId=node_id)
                self.canvas_vue.emit_sync_event(sync_event)

                logger.debug(f"Setup Vue observers for {node_id}")
        
        logger.debug(f"Successfully added node visual for {node_id}")
        return True
            
    def remove_node_visual(self, node_id: str) -> bool:
        """Remove a node's visual representation."""
        if node_id not in self.node_panels:
            return False
            
        # Remove all connected edges visually first
        edges_to_remove = []
        for connection_uuid, edge_wrapper in self.graph.edge_wrappers.items():
            if edge_wrapper.sink_node_id == node_id or edge_wrapper.source_node_id == node_id:
                edges_to_remove.append(connection_uuid)
        
        for connection_uuid in edges_to_remove:
            self.remove_connection_visual(connection_uuid)
        
        # Remove node visual
        if node_id in self.node_panels:
            ui_node = self.node_panels[node_id]
            ui_node.delete()
            del self.node_panels[node_id]
        
        # Remove from selection
        self.selected_nodes.discard(node_id)
        
        sync_event = SyncNodeObserverRemoveEvent(nodeId=node_id)
        self.canvas_vue.emit_sync_event(sync_event)
        
        return True

    def remove_all_node_visuals(self):
        """Remove all node visuals from the canvas."""
        node_ids = list(self.node_panels.keys())
        for node_id in node_ids:
            self.remove_node_visual(node_id)

    def update_node_position(self, node_id: str, position: Tuple[float, float]):
        """Update a node's visual position."""
        if node_id not in self.node_panels:
            return
            
        x, y = position
        container = self.node_panels[node_id].container
        container.style(f'left: {x}px; top: {y}px; z-index: 100;')
        container.update()
        
        self.node_panels[node_id].position = position
        
        sync_event = SyncNodePositionEvent(
            nodeId=node_id,
            position={'x': x, 'y': y}
        )
        self.canvas_vue.emit_sync_event(sync_event)
        
    def add_connection_visual(self, edge_wrapper: EdgeWrapper) -> bool:
        """Add a visual connection between two nodes."""
        connection_uuid = edge_wrapper.connection_uuid
        
        logger.debug(
            f"🔗 Creating connection visual: "
            f"{edge_wrapper.source_node_id}:{edge_wrapper.outlet_port_id} -> "
            f"{edge_wrapper.sink_node_id}:{edge_wrapper.inlet_port_id}"
        )
        
        # Create UIEdge instance
        ui_edge = UIEdge(
            wrapper=edge_wrapper,
            sync_event_emitter=self.canvas_vue.emit_sync_event
        )
        
        # Store reference
        self.connection_paths[connection_uuid] = ui_edge
        
        logger.debug(f"🔗 Created UIEdge and connection visual: {connection_uuid}")
        return True
   
    def remove_connection_visual(self, connection_uuid: str) -> bool:
        """Remove a connection's visual representation."""
        if connection_uuid not in self.connection_paths:
            return False
        
        # Cleanup UIEdge instance
        ui_edge = self.connection_paths.get(connection_uuid)
        if ui_edge:
            ui_edge.cleanup()
            del self.connection_paths[connection_uuid]
        
        # Emit removal sync event
        sync_event = SyncConnectionRemovalEvent(connectionUUID=connection_uuid)
        self.canvas_vue.emit_sync_event(sync_event)

        logger.debug(f"🔗 Removed UIEdge and connection visual: {connection_uuid}")
        return True

    def remove_all_connection_visuals(self):
        """Remove all connection visuals from the canvas."""
        connection_uuids = list(self.connection_paths.keys())
        for connection_uuid in connection_uuids:
            self.remove_connection_visual(connection_uuid)

    def sync_selections(self):
        """Helper method to emit the consolidated selection sync event."""
        sync_event = SyncSelectionsEvent(
            nodes=list(self.selected_nodes),
            connections=list(self.selected_connections)
        )
        self.canvas_vue.emit_sync_event(sync_event)

    def clear_all_visuals(self):
        """Clear all visual representations."""
        
        self.remove_all_connection_visuals()
        self.remove_all_node_visuals()

        # Clear local state
        self.node_panels.clear()
        self.connection_paths.clear()
        self.selected_nodes.clear()
        self.selected_connections.clear()

        sync_event = SyncCanvasClearEvent()        
        self.canvas_vue.emit_sync_event(sync_event)


    def cleanup(self):
        """Cleanup - unsubscribe from graph and clear resources."""
        logger.info(f"🔧 Shutting down GraphCanvasManager for {self.session_id} ...")
        
        # Cleanup canvas_vue first to prevent further client communication
        if self.canvas_vue:
            self.canvas_vue.cleanup()
        
        # Clear local state
        self.node_panels.clear()
        self.connection_paths.clear()
        self.selected_nodes.clear()
        self.selected_connections.clear()
        
        # Unsubscribe from graph events
        self.graph.unsubscribe_from_validation(self._on_validated)
        logger.info(f"🔧 GraphCanvasManager for {self.session_id} is shut down")


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
            node = self.graph.get_node_wrapper(node_id).node
            if node:
                positions.append((node.ui.state.posX, node.ui.state.posY))
        
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
                   