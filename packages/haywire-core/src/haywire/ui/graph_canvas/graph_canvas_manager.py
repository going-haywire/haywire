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
from haywire.core.node import BaseNode
from haywire.core.undo.actions.graph_actions import ClipboardData


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
    EdgeCreatedEvent,
    EdgeClickedEvent,
    SelectionChangedEvent,
    ContextMenuCanvasEvent,
    ContextMenuNodeEvent,
    ContextMenuEdgeEvent,
    ContextMenuSelectedEvent,
    NodeCreateRequestEvent,
    UserCopySelectedEvent,
    UserPasteClipboardEvent,
    SyncNodePositionEvent,
    SyncEdgeRemovalEvent,
    SyncSelectionsEvent,
    SyncCanvasClearEvent,
    ElementRedrawEvent,
    ElementResetEvent,
    ElementRevalidateEvent,
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
        skin_factory,
        node_factory,
        session_id: Optional[str] = None,
        on_selection_changed: Optional[Callable] = None,
    ):
        self.editor = editor
        self.skin_factory = skin_factory
        self.node_factory = node_factory
        self.session_id = session_id or "default"
        self._on_selection_changed = on_selection_changed

        # Access graph for read operations
        self.graph = editor.graph

        # Visual state
        self.node_panels: Dict[str, UINode] = {}  # node_id -> UINode
        self.edge_paths: Dict[str, UIEdge] = {}  # edge_id -> UIEdge object
        self.selected_nodes: Set[str] = set()
        self.selected_edges: Set[str] = set()

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
            "is_dragging": False,
            "dragged_elements": [],  # [{'type': 'node', 'id': 'node1'}, ...]
            "initial_positions": {},  # element_id -> {'x': x, 'y': y}
        }

        self._setup_canvas()

        # Subscribe for incremental updates.  sync_with_graph() handles the
        # initial state; every subsequent validation fires _on_validated().
        self.graph.subscribe_to_validation(self._on_validated)

        logger.info(f"🔧 GraphCanvasManager for {self.session_id} is setup")

    def _auto_register_event_handlers(self):
        """Automatically register event handlers using decorators"""
        logger.debug("🔧 Auto-registering event handlers...")

        for method_name in dir(self):
            method = getattr(self, method_name)
            if hasattr(method, "_handles_event_classes"):
                for event_class in method._handles_event_classes:
                    event_type = event_class.event_type
                    self._event_handlers[event_type] = method

        self._validate_handler_coverage()

    def _validate_handler_coverage(self):
        """Ensure all user events have registered handlers"""
        user_events = [
            event_type
            for event_type, event_class in GRAPH_EVENT_REGISTRY.items()
            if getattr(event_class, "category", "user") == "user"
        ]

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
        self.zoom_container = (
            ZoomPanContainer(min_zoom=0.1, max_zoom=3.0, initial_zoom=1.0)
            .classes("w-full flex-grow border-2 border-gray-300")
            .style("height: 100%;")
        )

        with self.zoom_container.content_container:
            self.canvas_vue = GraphCanvasVue(
                zoom_container=self.zoom_container, on_canvas_event=self._handle_canvas_event
            )

            self.context_menu = PopupContextMenu(
                node_factory=self.node_factory,
                on_emit_event=self._handle_canvas_event,
                clipboard_checker=self._has_clipboard_content,
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
                ui.notify(f"Error while processing {event.description}: {e}", type="negative")
                traceback.print_exc()
        else:
            logger.warning(f"No handler found for event type: {event_type}")

    # =============================================================================
    #
    #  EVENT HANDLERS
    #
    # =============================================================================

    # =============================================================================
    #  CONTEXT MENU EVENTS
    # =============================================================================

    @handles_event(
        ContextMenuCanvasEvent, ContextMenuNodeEvent, ContextMenuEdgeEvent, ContextMenuSelectedEvent
    )
    def process_context_menu(self, event):
        """Handle context menu events"""
        if isinstance(event, ContextMenuCanvasEvent):
            logger.debug(f"Canvas context menu at ({event.screenX}, {event.screenY})")
            if self.context_menu:
                self.context_menu.show_canvas_menu(
                    event.screenX, event.screenY, event.canvasX, event.canvasY
                )

        elif isinstance(event, ContextMenuNodeEvent):
            logger.debug(f"Node context menu for {event.nodeId} at ({event.screenX}, {event.screenY})")
            if self.context_menu:
                self.context_menu.show_node_menu(event.screenX, event.screenY, event.nodeId)

        elif isinstance(event, ContextMenuEdgeEvent):
            logger.debug(
                f"Connection context menu for {event.edge_id} at ({event.screenX}, {event.screenY})"
            )
            if self.context_menu:
                # Get metrics directly and pass to menu
                ui_edge = self.edge_paths.get(event.edge_id)
                if ui_edge and ui_edge.wrapper:
                    self.context_menu.show_edge_menu(
                        event.screenX,
                        event.screenY,
                        event.edge_id,
                        ui_edge.wrapper.edge,
                        ui_edge.wrapper.get_state(),
                    )

        elif isinstance(event, ContextMenuSelectedEvent):
            logger.debug(
                f"Selected context menu at ({event.screenX}, {event.screenY}) "
                f"for {len(event.selectedNodes)} nodes, "
                f"{len(event.selectedEdges)} connections"
            )
            if self.context_menu:
                self.context_menu.show_selected_menu(
                    event.screenX, event.screenY, event.selectedNodes, event.selectedEdges
                )

    # =============================================================================
    #  INTERACTION EVENTS
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

    @handles_event(EdgeClickedEvent)
    def process_edge_click(self, event: EdgeClickedEvent):
        """Handle edge click events"""
        try:
            logger.debug(f"Connection clicked: {event.edge_id}")
        except Exception as e:
            logger.error(f"Connection click handling failed: {e}")

    @handles_event(ElementRedrawEvent, ElementResetEvent, ElementRevalidateEvent)
    def process_update_element(self, event):
        """Handle element update requests by calling graph directly (bypasses undo history)."""

        if isinstance(event, ElementRedrawEvent):
            for node_id in event.nodes:
                self.graph.request_node_redraw(node_id)
            for edge_id in event.edges:
                self.graph.request_edge_redraw(edge_id)

        elif isinstance(event, ElementRevalidateEvent):
            for node_id in event.nodes:
                self.graph.request_node_revalidation(node_id)
            for edge_id in event.edges:
                self.graph.request_edge_revalidation(edge_id)

        elif isinstance(event, ElementResetEvent):
            for node_id in event.nodes:
                self.graph.request_node_reset(node_id)
            for edge_id in event.edges:
                self.graph.request_edge_reset(edge_id)

    # =============================================================================
    #  SELECTION EVENTS
    # =============================================================================

    @handles_event(SelectionChangedEvent)
    def process_selection_change(self, event: SelectionChangedEvent):
        """Handle selection changes"""
        logger.debug(f"Selection changed: nodes={event.selectedNodes}, connections={event.selectedEdges}")

        selected_nodes_set = set(event.selectedNodes)
        selected_edges_set = set(event.selectedEdges)

        # Update local state for fast canvas access
        self.selected_nodes = selected_nodes_set
        self.selected_edges = selected_edges_set

        # Notify session — GraphEditor._handle_selection_changed writes
        # the new selection into SessionContext (the canonical per-session store).
        if self._on_selection_changed is not None:
            self._on_selection_changed(selected_nodes_set, selected_edges_set)

    # =============================================================================
    # COPY PASTE EVENTS
    # =============================================================================

    @handles_event(UserCopySelectedEvent)
    def process_copy_selection(self, event: UserCopySelectedEvent):
        """Handle copying selected elements to clipboard."""
        logger.info(
            f"📋 Copying {len(event.selectedNodes)} nodes and {len(event.selectedEdges)} connections"
        )

        try:
            # Calculate bounding box for positioning
            bounding_box = self._calculate_selection_bounds(event.selectedNodes)

            # Store in session clipboard
            self.clipboard = ClipboardData(
                nodes=event.selectedNodes,
                edges=event.selectedEdges,
                original_to_new_ids={},  # Not needed for copy
                bounding_box=bounding_box,
                timestamp=time.time(),
                source_session_id=self.session_id,
            )

        except Exception as e:
            logger.error(f"❌ Error during copy operation: {e}")
            ui.notify(f"Copy failed: {e}", type="negative")
            traceback.print_exc()

    @handles_event(UserPasteClipboardEvent)
    def process_paste_clipboard(self, event: UserPasteClipboardEvent):
        """Handle pasting clipboard contents."""
        if not self.clipboard:
            logger.warning("❌ No clipboard content to paste")
            ui.notify("Nothing to paste", type="warning")
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
                new_node.props.posX = original_node.props.posX
                new_node.props.posY = original_node.props.posY
                
                new_nodes[new_node_id] = new_node
                id_mapping[original_node_id] = new_node_id
            
            # Create new edges with mapped node IDs
            new_edges = {}
            for conn_uuid, edge in valid_edges:
                if edge.output_node_id in id_mapping and edge.input_node_id in id_mapping:
                    new_conn_uuid = generate_edge_id(
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
                        edge_id=new_conn_uuid
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
    # CREATION / REMOVAL EVENTS
    # =============================================================================

    @handles_event(NodeCreateRequestEvent)
    def process_node_creation_request(self, event: NodeCreateRequestEvent):
        """Handle node creation requests from context menu or other sources."""
        logger.info(
            f"📝 Processing node creation request: {event.registryKey} "
            f"at ({event.position['x']}, {event.position['y']})"
        )

        try:
            wrapper = self.editor.create_wrapper(
                event.registryKey, (event.position["x"], event.position["y"])
            )

            if wrapper:
                logger.info(
                    f"✅ Created node {wrapper.node_id} at ({event.position['x']}, {event.position['y']})"
                )
                ui.notify(f"Created {event.registryKey} node", type="positive")
            else:
                ui.notify(f"Failed to create node of type: {event.registryKey}", type="negative")

        except Exception as e:
            logger.error(f"Error creating node: {e}")
            ui.notify(f"Error creating node: {e}", type="negative")

    @handles_event(EdgeCreatedEvent)
    def process_edge_creation(self, event: EdgeCreatedEvent):
        """Handle connection creation"""
        logger.debug(
            f"Creating connection: {event.sourceNodeId}:{event.outletPinId} -> "
            f"{event.sinkNodeId}:{event.inletPinId}"
        )

        if self.editor.create_edge(
            event.sourceNodeId, event.outletPinId, event.sinkNodeId, event.inletPinId
        ):
            ui.notify("Connection created")
        else:
            ui.notify("Failed to create connection", type="negative")

    @handles_event(UserRemoveEvent)
    def process_element_removal(self, event: UserRemoveEvent):
        """Handle unified element removal"""
        total_elements = len(event.nodes) + len(event.edges)
        logger.info(
            f"🗑️ Removing {total_elements} elements: {len(event.nodes)} nodes, {len(event.edges)} connections"
        )

        # Use the new unified removal method
        if self.editor.remove_elements(event.nodes, event.edges):
            ui.notify(f"Deleted {total_elements} element(s)", type="positive")
        else:
            ui.notify("Failed to delete elements", type="warning")

    # =============================================================================
    # SYNC UI with GRAPH STATE (unchanged from original)
    # =============================================================================

    def _on_validated(self, result: ValidationResult):
        """
        Handle validation results with flexible reason-based dispatch.
        """

        logger.info(f"🔄 Validation: {result.total_changes} changes in {result.validation_time_ms:.2f}ms")

        node_has_moved = False

        # Process nodes by reason
        for node_id, reason in result.nodes.items():
            if reason == ChangeReason.NODE_ADDED:
                # Create new UI node
                wrapper = self.graph.get_node_wrapper(node_id)
                if wrapper and node_id not in self.node_panels:
                    self.add_node_visual(wrapper.node, (wrapper.node.props.posX, wrapper.node.props.posY))
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
                        new_position = (node.props.posX, node.props.posY)
                        self.update_node_position(node_id, new_position)
                        node_has_moved = True
                        logger.debug(f"  ↔ Moved node: {node_id}")

            elif reason.requires_redraw():
                # Full redraw needed
                ui_node = self.node_panels.get(node_id)
                if ui_node:
                    self.refresh_node_visual(ui_node, reason)
                    logger.debug(f"  🔄 Redrawn node: {node_id} ({reason.value})")

        # Process edges by reason
        for edge_uuid, reason in result.edges.items():
            if reason == ChangeReason.EDGE_ADDED:
                # Create new UI edge
                wrapper = self.graph.get_edge_wrapper(edge_uuid)
                if wrapper and edge_uuid not in self.edge_paths:
                    self.add_edge_visual(wrapper)
                    logger.debug(f"  + Added edge UI: {edge_uuid}")

            elif reason == ChangeReason.EDGE_REMOVED:
                # Remove UI edge
                if edge_uuid in self.edge_paths:
                    self.remove_edge_visual(edge_uuid)
                    logger.debug(f"  - Removed edge UI: {edge_uuid}")

            elif reason.requires_redraw():
                # Full redraw needed
                ui_edge = self.edge_paths.get(edge_uuid)
                if ui_edge:
                    ui_edge.refresh(reason)  # Full re-render
                    logger.debug(f"  🔄 Redrawn edge: {edge_uuid} ({reason.value})")

        if node_has_moved:
            # self._update_connection_paths()
            pass

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
            f"🔄 Initial sync: {len(self.graph.node_wrappers)} nodes, {len(self.graph.edge_wrappers)} edges"
        )

        try:
            # Create synthetic validation result marking all elements as added
            synthetic_result = ValidationResult(
                nodes={node_id: ChangeReason.NODE_ADDED for node_id in self.graph.node_wrappers.keys()},
                edges={edge_uuid: ChangeReason.EDGE_ADDED for edge_uuid in self.graph.edge_wrappers.keys()},
                validation_time_ms=0.0,
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
            with (
                ui.element("div")
                .classes("absolute")
                .style(f"left: {x}px; top: {y}px; z-index: 100; transform-origin: top-left; cursor: move;")
                .props(f'id="{node_id}" data-node-id="{node_id}" ') as container
            ):
                logger.debug(f"Created container for node {node_id}")

                # Create UINode with wrapper reference for hot reload support
                ui_node = UINode(container, wrapper, self.skin_factory)
                # Register sync event emitter for hot reload updates after
                # the refresh() call. we need to wait until the UI is rendered.
                ui_node.register_sync_event_emitter(self.canvas_vue.emit_sync_event)
                ui_node.refresh(ChangeReason.NODE_ADDED)

                logger.debug(f"Rendered UINode for {node_id}")

                ui_node.position = position
                self.node_panels[node_id] = ui_node

                logger.debug(f"Setup Vue observers for {node_id}")

        logger.debug(f"Successfully added node visual for {node_id}")
        return True

    def refresh_node_visual(self, ui_node: UINode, reason: ChangeReason) -> bool:
        """Refresh a node's visual representation."""
        ui_node.refresh(reason)  # Full re-render

    def remove_node_visual(self, node_id: str) -> bool:
        """Remove a node's visual representation."""
        if node_id not in self.node_panels:
            return False

        # Remove all connected edges visually first
        edges_to_remove = []
        for edge_id, edge_wrapper in self.graph.edge_wrappers.items():
            if edge_wrapper.sink_node_id == node_id or edge_wrapper.source_node_id == node_id:
                edges_to_remove.append(edge_id)

        for edge_id in edges_to_remove:
            self.remove_edge_visual(edge_id)

        # Remove node visual
        if node_id in self.node_panels:
            ui_node = self.node_panels[node_id]
            ui_node.delete()
            del self.node_panels[node_id]

        # Remove from selection
        self.selected_nodes.discard(node_id)

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
        container.style(f"left: {x}px; top: {y}px; z-index: 100;")
        container.update()

        self.node_panels[node_id].position = position

        sync_event = SyncNodePositionEvent(nodeId=node_id, position={"x": x, "y": y})
        self.canvas_vue.emit_sync_event(sync_event)

    def add_edge_visual(self, edge_wrapper: EdgeWrapper) -> bool:
        """Add a visual edge between two nodes."""
        edge_id = edge_wrapper.edge_id

        logger.debug(
            f"🔗 Creating edge visual: "
            f"{edge_wrapper.source_node_id}:{edge_wrapper.outlet_port_id} -> "
            f"{edge_wrapper.sink_node_id}:{edge_wrapper.inlet_port_id}"
        )

        # Create UIEdge instance
        ui_edge = UIEdge(wrapper=edge_wrapper, sync_event_emitter=self.canvas_vue.emit_sync_event)

        # Store reference
        self.edge_paths[edge_id] = ui_edge

        logger.debug(f"🔗 Created UIEdge and connection visual: {edge_id}")
        return True

    def remove_edge_visual(self, edge_id: str) -> bool:
        """Remove a connection's visual representation."""
        if edge_id not in self.edge_paths:
            return False

        # Cleanup UIEdge instance
        ui_edge = self.edge_paths.get(edge_id)
        if ui_edge:
            ui_edge.cleanup()
            del self.edge_paths[edge_id]

        # Emit removal sync event
        sync_event = SyncEdgeRemovalEvent(edge_id=edge_id)
        self.canvas_vue.emit_sync_event(sync_event)

        logger.debug(f"🔗 Removed UIEdge and connection visual: {edge_id}")
        return True

    def remove_all_edge_visuals(self):
        """Remove all connection visuals from the canvas."""
        edge_ids = list(self.edge_paths.keys())
        for edge_id in edge_ids:
            self.remove_edge_visual(edge_id)

    def sync_selections(self):
        """Helper method to emit the consolidated selection sync event."""
        sync_event = SyncSelectionsEvent(nodes=list(self.selected_nodes), edges=list(self.selected_edges))
        self.canvas_vue.emit_sync_event(sync_event)

    def clear_all_visuals(self):
        """Clear all visual representations."""

        self.remove_all_edge_visuals()
        self.remove_all_node_visuals()

        # Clear local state
        self.node_panels.clear()
        self.edge_paths.clear()
        self.selected_nodes.clear()
        self.selected_edges.clear()

        sync_event = SyncCanvasClearEvent()
        self.canvas_vue.emit_sync_event(sync_event)

    def cleanup(self):
        """Cleanup - unsubscribe from graph and clear resources."""
        logger.info(f"🔧 Shutting down GraphCanvasManager for {self.session_id} ...")

        # Stop receiving validation events before tearing down UI
        try:
            self.graph.unsubscribe_from_validation(self._on_validated)
        except Exception as exc:
            logger.warning(f"GraphCanvasManager: unsubscribe error: {exc}")

        # Cleanup canvas_vue first to prevent further client communication
        if self.canvas_vue:
            self.canvas_vue.cleanup()

        # Clear local state
        self.node_panels.clear()
        self.edge_paths.clear()
        self.selected_nodes.clear()
        self.selected_edges.clear()

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
            return {"min_x": 0, "min_y": 0, "max_x": 0, "max_y": 0}

        positions = []
        for node_id in node_ids:
            node = self.graph.get_node_wrapper(node_id).node
            if node:
                positions.append((node.props.posX, node.props.posY))

        if not positions:
            return {"min_x": 0, "min_y": 0, "max_x": 0, "max_y": 0}

        min_x = min(pos[0] for pos in positions)
        min_y = min(pos[1] for pos in positions)
        max_x = max(pos[0] for pos in positions)
        max_y = max(pos[1] for pos in positions)

        return {"min_x": min_x, "min_y": min_y, "max_x": max_x, "max_y": max_y}
