# Corrected Streamlined Event System Implementation Guide

## Overview

The streamlined dict approach eliminates the current complex callback system by implementing a unified bidirectional event protocol. This reduces 34+ individual methods across three files to just 5 unified event handlers, while maintaining consistent data formats throughout the stack.

## Core Principles

1. **Consistent Field Names**: Use `camelCase` throughout (Vue/JS native format)
2. **Direct Object Passing**: No field remapping between layers
3. **Unified Event Handlers**: Single entry point per direction per file
4. **Semantic Event Names**: Clear intent-based naming

---

## Core Event Structure

All events follow this consistent structure across the entire system:

```python
# Upstream Events (Vue → Python)
{
    'event_type': str,           # 'nodePositionChanged', 'connectionCreated', etc.
    'source_session_id': str,    # Session that originated the event
    'timestamp': float,          # When the event occurred
    'data': Dict[str, Any],      # Event payload with consistent field names
    'requires_broadcast': bool   # Whether to sync to other sessions
}

# Downstream Events (Python → Vue)  
{
    'event_type': str,           # 'syncNodePosition', 'syncConnectionAddition', etc.
    'timestamp': float,          # When the event was created
    'data': Dict[str, Any]       # Event payload with consistent field names
}
```

## Unified Field Names

**Key principle**: Use **camelCase throughout** to match JavaScript conventions and eliminate field remapping:

```python
# Standard field names used everywhere:
{
    'nodeId': str,
    'position': {'x': float, 'y': float},
    'connectionId': str, 
    'outputNodeId': str,
    'outletPinId': str,
    'inputNodeId': str,
    'inletPinId': str,
    'selectedNodes': List[str],
    'selectedConnections': List[str]
}
```

## Event Type Definitions

First, create shared event definitions:

```python
class GraphEvents:
    """Event type definitions for graph canvas communication."""
    
    # Upstream Events (Vue → Python)
    class UserInteractions:
        NODE_CREATED = 'nodeCreated'
        CONNECTION_CREATED = 'connectionCreated'
        CONNECTION_REMOVED = 'connectionRemoved'
        CONNECTION_CLICKED = 'connectionClicked'
        NODE_POSITION_CHANGED = 'nodePositionChanged'
        NODE_DRAG_START = 'nodeDragStart'
        NODE_DRAG_END = 'nodeDragEnd'
        SELECTION_CHANGED = 'selectionChanged'
        CONTEXT_MENU_CANVAS = 'contextMenuCanvas'
        CONTEXT_MENU_NODE = 'contextMenuNode'
        CONTEXT_MENU_CONNECTION = 'contextMenuConnection'
    
    # Downstream Events (Python → Vue)
    class SyncCommands:
        SYNC_NODE_ADDITION = 'syncNodeAddition'
        SYNC_NODE_REMOVAL = 'syncNodeRemoval'
        SYNC_NODE_POSITION = 'syncNodePosition'
        SYNC_CONNECTION_ADDITION = 'syncConnectionAddition'
        SYNC_CONNECTION_REMOVAL = 'syncConnectionRemoval'
        SYNC_SELECTION_STATE = 'syncSelectionState'
        SYNC_NODE_OBSERVER = 'syncNodeObserver'
        SYNC_CONNECTIONS_FOR_NODE = 'syncConnectionsForNode'
        SYNC_ALL_CONNECTIONS = 'syncAllConnections'
        SYNC_CANVAS_CLEAR = 'syncCanvasClear'
```

```javascript
export const GraphEvents = {
  UserInteractions: {
    NODE_CREATED: 'nodeCreated',
    CONNECTION_CREATED: 'connectionCreated',
    CONNECTION_REMOVED: 'connectionRemoved',
    CONNECTION_CLICKED: 'connectionClicked',
    NODE_POSITION_CHANGED: 'nodePositionChanged',
    NODE_DRAG_START: 'nodeDragStart',
    NODE_DRAG_END: 'nodeDragEnd',
    SELECTION_CHANGED: 'selectionChanged',
    CONTEXT_MENU_CANVAS: 'contextMenuCanvas',
    CONTEXT_MENU_NODE: 'contextMenuNode',
    CONTEXT_MENU_CONNECTION: 'contextMenuConnection'
  },
  
  SyncCommands: {
    SYNC_NODE_ADDITION: 'syncNodeAddition',
    SYNC_NODE_REMOVAL: 'syncNodeRemoval',
    SYNC_NODE_POSITION: 'syncNodePosition',
    SYNC_CONNECTION_ADDITION: 'syncConnectionAddition',
    SYNC_CONNECTION_REMOVAL: 'syncConnectionRemoval',
    SYNC_SELECTION_STATE: 'syncSelectionState',
    SYNC_NODE_OBSERVER: 'syncNodeObserver',
    SYNC_CONNECTIONS_FOR_NODE: 'syncConnectionsForNode',
    SYNC_ALL_CONNECTIONS: 'syncAllConnections',
    SYNC_CANVAS_CLEAR: 'syncCanvasClear'
  }
}
```

---

## File 1: graph_canvas.vue (Frontend)

### **Current State → New Implementation**

**REMOVE**: Individual event emitters scattered throughout methods
**ADD**: Unified event emission system

```vue
<script>
import { GraphEvents } from './graph_events.js';

export default {
    name: 'GraphCanvas',
    
    methods: {
        // =============================================================================
        // NEW: UNIFIED EVENT EMISSION SYSTEM
        // =============================================================================
        
        emitCanvasEvent(eventType, data, requiresBroadcast = true) {
            /**
             * Unified event emitter - replaces all individual $emit calls
             */
            const event = {
                event_type: eventType,
                source_session_id: this.sessionId || 'default',
                timestamp: Date.now(),
                data: data,
                requires_broadcast: requiresBroadcast
            };
            
            console.log(`🔄 Vue→Python Event: ${eventType}`, data);
            this.$emit('canvasEvent', event);
        },
        
        // =============================================================================
        // NEW: UNIFIED SYNC EVENT HANDLER  
        // =============================================================================
        
        handleSyncEvent(event) {
            /**
             * Unified sync event handler - replaces all individual method calls from Python
             */
            const { event_type, data } = event;
            console.log(`🔄 Python→Vue Event: ${event_type}`, data);
            
            const handlers = {
                [GraphEvents.SyncCommands.SYNC_NODE_ADDITION]: this.handleSyncNodeAddition,
                [GraphEvents.SyncCommands.SYNC_NODE_REMOVAL]: this.handleSyncNodeRemoval,
                [GraphEvents.SyncCommands.SYNC_NODE_POSITION]: this.handleSyncNodePosition,
                [GraphEvents.SyncCommands.SYNC_CONNECTION_ADDITION]: this.handleSyncConnectionAddition,
                [GraphEvents.SyncCommands.SYNC_CONNECTION_REMOVAL]: this.handleSyncConnectionRemoval,
                [GraphEvents.SyncCommands.SYNC_SELECTION_STATE]: this.handleSyncSelectionState,
                [GraphEvents.SyncCommands.SYNC_NODE_OBSERVER]: this.handleSyncNodeObserver,
                [GraphEvents.SyncCommands.SYNC_CONNECTIONS_FOR_NODE]: this.handleSyncConnectionsForNode,
                [GraphEvents.SyncCommands.SYNC_ALL_CONNECTIONS]: this.handleSyncAllConnections,
                [GraphEvents.SyncCommands.SYNC_CANVAS_CLEAR]: this.handleSyncCanvasClear
            };
            
            const handler = handlers[event_type];
            if (handler) {
                handler(data);
            } else {
                console.warn(`Unhandled sync event: ${event_type}`);
            }
        },
        
        // =============================================================================
        // MODIFIED: USER INTERACTION HANDLERS (Now use unified emission)
        // =============================================================================
        
        handleNodeCreated(nodeId, position) {
            this.emitCanvasEvent(GraphEvents.UserInteractions.NODE_CREATED, {
                nodeId,
                position
            });
        },
        
        handleNodePositionChange(nodeId, x, y, positionChanged) {
            if (positionChanged) {
                this.emitCanvasEvent(GraphEvents.UserInteractions.NODE_POSITION_CHANGED, {
                    nodeId,
                    position: { x, y }
                });
            }
        },
        
        handleConnectionCreated(startNodeId, startPort, endNodeId, endPort) {
            this.emitCanvasEvent(GraphEvents.UserInteractions.CONNECTION_CREATED, {
                outputNodeId: startNodeId,
                outletPinId: startPort,
                inputNodeId: endNodeId,
                inletPinId: endPort
            });
        },
        
        handleConnectionRemoved(connectionId) {
            this.emitCanvasEvent(GraphEvents.UserInteractions.CONNECTION_REMOVED, {
                connectionId
            });
        },
        
        handleConnectionClicked(connectionId) {
            this.emitCanvasEvent(GraphEvents.UserInteractions.CONNECTION_CLICKED, {
                connectionId
            });
        },
        
        handleNodeDragStart(nodeId) {
            this.emitCanvasEvent(GraphEvents.UserInteractions.NODE_DRAG_START, {
                nodeId
            });
        },
        
        handleNodeDragEnd(nodeId, positionChanged) {
            this.emitCanvasEvent(GraphEvents.UserInteractions.NODE_DRAG_END, {
                nodeId,
                positionChanged
            });
        },
        
        handleSelectionChanged() {
            this.emitCanvasEvent(GraphEvents.UserInteractions.SELECTION_CHANGED, {
                selectedNodes: Array.from(this.selectedNodes),
                selectedConnections: Array.from(this.selectedConnections)
            });
        },
        
        handleContextMenu(event, targetType, targetId = null) {
            event.preventDefault();
            
            const baseData = {
                screenX: event.clientX,
                screenY: event.clientY,
                canvasX: event.offsetX,
                canvasY: event.offsetY
            };
            
            if (targetType === 'canvas') {
                this.emitCanvasEvent(GraphEvents.UserInteractions.CONTEXT_MENU_CANVAS, baseData);
            } else if (targetType === 'node') {
                this.emitCanvasEvent(GraphEvents.UserInteractions.CONTEXT_MENU_NODE, {
                    ...baseData,
                    nodeId: targetId
                });
            } else if (targetType === 'connection') {
                this.emitCanvasEvent(GraphEvents.UserInteractions.CONTEXT_MENU_CONNECTION, {
                    ...baseData,
                    connectionId: targetId
                });
            }
        },
        
        // =============================================================================
        // NEW: SYNC EVENT HANDLERS (Replace direct method calls from Python)
        // =============================================================================
        
        handleSyncNodeAddition(data) {
            const { nodeId, position } = data;
            this.$nextTick(() => {
                const nodeElement = document.getElementById(nodeId);
                if (nodeElement) {
                    nodeElement.style.left = `${position.x}px`;
                    nodeElement.style.top = `${position.y}px`;
                    this.addNodeObserver(nodeId);
                    console.log(`✅ Synced node addition: ${nodeId}`);
                }
            });
        },
        
        handleSyncNodeRemoval(data) {
            const { nodeId } = data;
            this.removeNodeObserver(nodeId);
            // Node DOM removal is handled by Python/NiceGUI
            console.log(`✅ Synced node removal: ${nodeId}`);
        },
        
        handleSyncNodePosition(data) {
            const { nodeId, position } = data;
            const nodeElement = document.getElementById(nodeId);
            if (nodeElement) {
                nodeElement.style.left = `${position.x}px`;
                nodeElement.style.top = `${position.y}px`;
                this.updateConnectionsForNode(nodeId);
                console.log(`✅ Synced node position: ${nodeId}`);
            }
        },
        
        handleSyncConnectionAddition(data) {
            // Data is already in correct format - direct usage!
            this.connections.push(data);
            console.log(`✅ Synced connection addition: ${data.connectionId}`);
        },
        
        handleSyncConnectionRemoval(data) {
            const { connectionId } = data;
            const index = this.connections.findIndex(c => c.connectionId === connectionId);
            if (index > -1) {
                this.connections.splice(index, 1);
                console.log(`✅ Synced connection removal: ${connectionId}`);
            }
        },
        
        handleSyncSelectionState(data) {
            const { selectedNodes, selectedConnections, action } = data;
            
            if (action === 'clear') {
                this.clearSelection();
            } else {
                // Direct array usage - no field remapping
                this.clearSelection();
                selectedNodes.forEach(nodeId => this.selectNode(nodeId, true));
                selectedConnections.forEach(connId => this.selectConnection(connId, true));
            }
            console.log(`✅ Synced selection state`);
        },
        
        handleSyncNodeObserver(data) {
            const { nodeId, action } = data;
            if (action === 'add') {
                this.addNodeObserver(nodeId);
            } else if (action === 'remove') {
                this.removeNodeObserver(nodeId);
            }
            console.log(`✅ Synced node observer: ${action} ${nodeId}`);
        },
        
        handleSyncConnectionsForNode(data) {
            const { nodeId } = data;
            this.updateConnectionsForNode(nodeId);
            console.log(`✅ Synced connections for node: ${nodeId}`);
        },
        
        handleSyncAllConnections(data) {
            const { connections } = data;
            // Replace entire connections array with synced data
            this.connections.splice(0, this.connections.length, ...connections);
            console.log(`✅ Synced all connections: ${connections.length} connections`);
        },
        
        handleSyncCanvasClear(data) {
            this.clearSelection();
            this.connections.splice(0);
            // Node clearing handled by Python/NiceGUI
            console.log(`✅ Synced canvas clear`);
        }
    },
    
    mounted() {
        // Expose unified sync handler to Python
        this.$el._graphCanvasControls = {
            ...this.$el._graphCanvasControls,
            handleSyncEvent: this.handleSyncEvent
        };
    }
}
</script>
```

### **Key Changes for Vue Component:**

1. **REMOVE** all individual `$emit` calls
2. **ADD** `emitCanvasEvent()` - single emission method
3. **ADD** `handleSyncEvent()` - single sync handler
4. **MODIFY** existing event handlers to use unified emission
5. **REPLACE** direct method calls with sync event handlers
6. **ADD** missing handlers: `handleNodeCreated`, `handleConnectionRemoved`
7. **ADD** new sync handlers: `handleSyncNodeObserver`, `handleSyncConnectionsForNode`, `handleSyncAllConnections`

---

## File 2: graph_canvas_vue.py (Python Wrapper)

### **Current State → New Implementation**

**REMOVE**: 11+ individual callback handlers + 10+ individual method calls
**ADD**: 2 unified handlers (1 upstream, 1 downstream)

```python
from .graph_events import GraphEvents

class GraphCanvasVue(ui.element, component='graph_canvas.vue'):
    """Vue-based graph canvas component with streamlined event handling."""
    
    def __init__(self, 
                 on_canvas_event: Optional[Callable[[dict], None]] = None,
                 zoom_container=None,
                 canvas_width: int = 8000, 
                 canvas_height: int = 8000):
        super().__init__()
        
        # =============================================================================
        # NEW: UNIFIED EVENT CALLBACK
        # =============================================================================
        self._on_canvas_event = on_canvas_event  # Single callback replaces 11+ callbacks
        
        # Store zoom container reference
        self.zoom_container = zoom_container
        
        # Props for Vue component  
        self._props['canvasWidth'] = canvas_width
        self._props['canvasHeight'] = canvas_height
        self._props['connections'] = []
        self._props['data-graph_canvas'] = True
        
        # =============================================================================
        # NEW: UNIFIED EVENT HANDLER SETUP
        # =============================================================================
        self.on('canvasEvent', self._handle_canvas_event)  # Single handler replaces 11+ handlers
    
    # =============================================================================
    # NEW: UNIFIED UPSTREAM EVENT HANDLER
    # =============================================================================
    
    def _handle_canvas_event(self, event_data):
        """
        Unified canvas event handler - replaces all individual _handle_* methods
        
        REPLACES:
        - _handle_node_created()
        - _handle_connection_created() 
        - _handle_connection_removed()
        - _handle_connection_clicked()
        - _handle_node_position_changed()
        - _handle_node_drag_start()
        - _handle_node_drag_end()
        - _handle_selection_changed()
        - _handle_context_menu_canvas()
        - _handle_context_menu_node()
        - _handle_context_menu_connection()
        """
        if self._on_canvas_event and hasattr(event_data, 'args'):
            event = event_data.args
            event_type = event.get('event_type')
            
            # Log for debugging
            print(f"🔄 Vue→Python Event: {event_type} | Data: {event.get('data', {})}")
            
            # Pass event directly to manager - no field remapping!
            self._on_canvas_event(event)
    
    # =============================================================================
    # NEW: UNIFIED DOWNSTREAM EVENT HANDLER
    # =============================================================================
    
    def handle_sync_event(self, event: dict):
        """
        Unified sync event handler - replaces all individual method calls
        
        REPLACES:
        - add_connection_visual()
        - remove_connection_visual()
        - sync_connections_from_edges() 
        - update_connections_for_node()
        - add_node_observer()
        - remove_node_observer()
        - select_node()
        - deselect_node()
        - select_connection()
        - deselect_connection()
        - clear_selection()
        - sync_all_connections()
        """
        event_type = event.get('event_type')
        data = event.get('data', {})
        
        # Log for debugging
        print(f"🔄 Python→Vue Event: {event_type} | Data: {data}")
        
        # Handle different sync event types
        if event_type == GraphEvents.SyncCommands.SYNC_CONNECTION_ADDITION:
            self._handle_sync_connection_addition(data)
            
        elif event_type == GraphEvents.SyncCommands.SYNC_CONNECTION_REMOVAL:
            self._handle_sync_connection_removal(data)
            
        elif event_type == GraphEvents.SyncCommands.SYNC_ALL_CONNECTIONS:
            self._handle_sync_all_connections(data)
            
        elif event_type == GraphEvents.SyncCommands.SYNC_SELECTION_STATE:
            self._handle_sync_selection_state(data)
            
        elif event_type in [
            GraphEvents.SyncCommands.SYNC_NODE_ADDITION,
            GraphEvents.SyncCommands.SYNC_NODE_REMOVAL,
            GraphEvents.SyncCommands.SYNC_NODE_POSITION,
            GraphEvents.SyncCommands.SYNC_NODE_OBSERVER,
            GraphEvents.SyncCommands.SYNC_CONNECTIONS_FOR_NODE,
            GraphEvents.SyncCommands.SYNC_CANVAS_CLEAR
        ]:
            # Pass through to Vue component
            self.run_method('handleSyncEvent', event)
            
        else:
            print(f"Unhandled sync event type: {event_type}")
    
    # =============================================================================
    # PRIVATE: SPECIFIC SYNC HANDLERS  
    # =============================================================================
    
    def _handle_sync_connection_addition(self, data):
        """Handle connection addition - direct data usage."""
        # Add to connections prop directly - no field remapping!
        current_connections = list(self._props.get('connections', []))
        
        # Remove existing connection with same ID if it exists
        connection_id = data.get('connectionId')
        current_connections = [c for c in current_connections if c.get('connectionId') != connection_id]
        
        # Add new connection - data is already in correct format
        current_connections.append(data)
        self._props['connections'] = current_connections
        
        print(f"✅ Connection added to props: {connection_id}")
    
    def _handle_sync_connection_removal(self, data):
        """Handle connection removal - direct data usage."""
        connection_id = data.get('connectionId')
        current_connections = list(self._props.get('connections', []))
        
        # Filter out connection - direct ID matching
        updated_connections = [c for c in current_connections if c.get('connectionId') != connection_id]
        self._props['connections'] = updated_connections
        
        print(f"✅ Connection removed from props: {connection_id}")
    
    def _handle_sync_all_connections(self, data):
        """Handle full connection sync - direct data usage."""
        connections = data.get('connections', [])
        self._props['connections'] = connections
        
        # Also pass through to Vue component for visual sync
        self.run_method('handleSyncEvent', {
            'event_type': GraphEvents.SyncCommands.SYNC_ALL_CONNECTIONS,
            'data': data
        })
        
        print(f"✅ All connections synced: {len(connections)} connections")
    
    def _handle_sync_selection_state(self, data):
        """Handle selection state sync - direct data usage."""
        # Pass through to Vue component - data is already in correct format
        self.run_method('handleSyncEvent', {
            'event_type': GraphEvents.SyncCommands.SYNC_SELECTION_STATE,
            'data': data
        })
    
    # =============================================================================
    # LEGACY COMPATIBILITY METHODS (Optional - for gradual migration)
    # =============================================================================
    
    def add_connection_visual(self, connection_id: str, from_pin_id: str, to_pin_id: str):
        """Legacy method - routes to event system."""
        print("⚠️  Using legacy add_connection_visual - consider upgrading to event system")
        
        # Parse pin IDs and convert to event format
        from_parts = from_pin_id.split(':')
        to_parts = to_pin_id.split(':')
        
        if len(from_parts) == 2 and len(to_parts) == 2:
            data = {
                'connectionId': connection_id,
                'outputNodeId': from_parts[0],
                'outletPinId': from_parts[1],
                'inputNodeId': to_parts[0],
                'inletPinId': to_parts[1]
            }
            self.handle_sync_event({
                'event_type': GraphEvents.SyncCommands.SYNC_CONNECTION_ADDITION,
                'data': data
            })
    
    def sync_all_connections(self, connections: List[dict]):
        """Legacy method - routes to event system."""
        print("⚠️  Using legacy sync_all_connections - consider upgrading to event system")
        self.handle_sync_event({
            'event_type': GraphEvents.SyncCommands.SYNC_ALL_CONNECTIONS,
            'data': {'connections': connections}
        })
    
    def clear_selection(self):
        """Legacy method - routes to event system."""
        print("⚠️  Using legacy clear_selection - consider upgrading to event system")
        self.handle_sync_event({
            'event_type': GraphEvents.SyncCommands.SYNC_SELECTION_STATE,
            'data': {'action': 'clear'}
        })
```

### **Key Changes for GraphCanvasVue:**

1. **REMOVE** 11+ individual callback parameters from `__init__()`
2. **ADD** single `on_canvas_event` callback
3. **REMOVE** 11+ individual event handlers
4. **ADD** single `_handle_canvas_event()` handler  
5. **REMOVE** 10+ individual method calls
6. **ADD** single `handle_sync_event()` method
7. **ADD** specific handlers for connection management and all-connections sync
8. **ADD** legacy compatibility methods for gradual migration

---

## File 3: graph_canvas_manager.py (Business Logic)

### **Current State → New Implementation**

**REMOVE**: 11+ callback handlers + 10+ visual update methods
**ADD**: 1 unified event router + 1 unified event emitter

```python
from .graph_events import GraphEvents
import time

class GraphCanvasManager:
    """Graph canvas manager with streamlined event system."""
    
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
        # ... existing initialization ...
        
        # =============================================================================
        # REMOVE: Individual callback parameters
        # ADD: Single event callback
        # =============================================================================
        self._vue_event_queue = []  # Queue events if Vue isn't ready
        
        self._setup_canvas()
    
    def _setup_canvas(self):
        """Setup canvas with streamlined event system."""
        print("🔧 Setting up GraphCanvasManager with streamlined events")
        
        # Create zoom container
        self.zoom_container = ZoomPanContainer(
            min_zoom=0.1,
            max_zoom=3.0,
            initial_zoom=1.0
        ).classes('w-full flex-grow border-2 border-gray-300').style('height: calc(100% - 60px);')
        
        # =============================================================================
        # NEW: UNIFIED EVENT SETUP
        # =============================================================================
        with self.zoom_container.content_container:
            self.canvas_vue = GraphCanvasVue(
                zoom_container=self.zoom_container,
                on_canvas_event=self._handle_canvas_event  # Single callback replaces 11+ callbacks!
            )
            
            self.context_menu = PopupContextMenu(
                available_nodes=self.available_nodes,
                on_create_node=self._handle_context_create_node,
                on_duplicate_node=self._handle_context_duplicate_node,
                on_copy_node=self._handle_context_copy_node,
                on_delete_node=self._handle_context_delete_node,
                on_inspect_connection=self._handle_context_inspect_connection,
                on_delete_connection=self._handle_context_delete_connection
            )
    
    # =============================================================================
    # NEW: UNIFIED UPSTREAM EVENT HANDLER
    # =============================================================================
    
    def _handle_canvas_event(self, event: dict):
        """
        Unified canvas event router - replaces all individual callback handlers
        
        REPLACES:
        - _handle_vue_node_created()
        - _handle_vue_connection_created()
        - _handle_vue_connection_removed()
        - _handle_vue_connection_clicked()
        - _handle_vue_node_position_changed()
        - _handle_vue_node_drag_start()
        - _handle_vue_node_drag_end()
        - _handle_vue_selection_changed()
        - _handle_vue_context_menu_*()
        """
        event_type = event.get('event_type')
        data = event.get('data', {})
        source_session_id = event.get('source_session_id')
        
        # Log for debugging
        print(f"🔄 Canvas Event Router: {event_type} | Session: {source_session_id}")
        
        # Route to appropriate handlers
        handlers = {
            GraphEvents.UserInteractions.NODE_CREATED: self._handle_node_created,
            GraphEvents.UserInteractions.CONNECTION_CREATED: self._handle_connection_created,
            GraphEvents.UserInteractions.CONNECTION_REMOVED: self._handle_connection_removed,
            GraphEvents.UserInteractions.CONNECTION_CLICKED: self._handle_connection_clicked,
            GraphEvents.UserInteractions.NODE_POSITION_CHANGED: self._handle_node_position_changed,
            GraphEvents.UserInteractions.NODE_DRAG_START: self._handle_node_drag_start,
            GraphEvents.UserInteractions.NODE_DRAG_END: self._handle_node_drag_end,
            GraphEvents.UserInteractions.SELECTION_CHANGED: self._handle_selection_changed,
            GraphEvents.UserInteractions.CONTEXT_MENU_CANVAS: self._handle_context_menu_canvas,
            GraphEvents.UserInteractions.CONTEXT_MENU_NODE: self._handle_context_menu_node,
            GraphEvents.UserInteractions.CONTEXT_MENU_CONNECTION: self._handle_context_menu_connection
        }
        
        handler = handlers.get(event_type)
        if handler:
            handler(event, data)
        else:
            print(f"Unhandled canvas event: {event_type}")
    
    # =============================================================================
    # NEW: SPECIFIC EVENT HANDLERS (Direct data usage)
    # =============================================================================
    
    def _handle_node_created(self, event: dict, data: dict):
        """Handle node creation - direct data usage."""
        try:
            node_id = data['nodeId']
            position = data['position']
            x, y = position['x'], position['y']
            
            print(f"Node creation request: {node_id} at ({x}, {y})")
            
            # Create node through existing mechanisms
            # This would integrate with your node creation logic
            
            # Emit sync event to update visuals
            self._emit_to_vue(GraphEvents.SyncCommands.SYNC_NODE_ADDITION, {
                'nodeId': node_id,
                'position': {'x': x, 'y': y}
            })
            
        except Exception as e:
            print(f"Node creation failed: {e}")
    
    def _handle_connection_created(self, event: dict, data: dict):
        """Handle connection creation - direct data usage."""
        try:
            # Use data fields directly - no remapping!
            output_node_id = data['outputNodeId']
            outlet_pin_id = data['outletPinId'] 
            input_node_id = data['inputNodeId']
            inlet_pin_id = data['inletPinId']
            
            print(f"Connection request: {output_node_id}:{outlet_pin_id} -> {input_node_id}:{inlet_pin_id}")
            
            # Create edge
            edge = Edge(
                edge_type=EdgeType.DATA,
                output_node_id=output_node_id,
                outlet_pin_id=outlet_pin_id,
                input_node_id=input_node_id,
                inlet_pin_id=inlet_pin_id
            )