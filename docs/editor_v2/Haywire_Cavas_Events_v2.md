# Enhanced Event System Implementation Guide

## Overview

The enhanced event system eliminates complex callback management by implementing a class-based, type-safe bidirectional event protocol with automatic code generation. This reduces 34+ individual methods across three files to a unified auto-registration system, while maintaining consistent data formats and providing compile-time safety.

## Core Principles

1. **Class-Based Event Definitions**: Single source of truth using Python dataclasses
2. **Type-Safe Registration**: Event handlers registered using event classes, not strings
3. **Build-Time Code Generation**: Vue constants automatically generated from Python definitions
4. **Unified Event Routing**: Single entry point with automatic handler discovery
5. **Semantic Event Names**: Clear intent-based naming with IDE support

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

## Event Definitions System

### 1. Event Registry and Decorator

Create the foundational registry system:

```python
# event_definitions.py
import dataclasses
import time
from dataclasses import dataclass, field
from typing import Dict, Any, List, Type

# Global registry for all event types
GRAPH_EVENT_REGISTRY: Dict[str, Type] = {}

def graph_event(event_type: str, category: str = "user", description: str = ""):
    """Decorator to register event classes in the global registry"""
    def decorator(cls):
        cls.event_type = event_type
        cls.category = category
        cls.description = description
        GRAPH_EVENT_REGISTRY[event_type] = cls
        return cls
    return decorator

@dataclass
class BaseGraphEvent:
    """Base class for all graph events with serialization support"""
    source_session_id: str = field(default="default")
    timestamp: float = field(default_factory=time.time)
    requires_broadcast: bool = field(default=True)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to wire format"""
        event_data = {}
        for datafield in dataclasses.fields(self):
            if datafield.name not in ['source_session_id', 'timestamp', 'requires_broadcast']:
                event_data[datafield.name] = getattr(self, datafield.name)
        
        return {
            'event_type': self.event_type,
            'source_session_id': self.source_session_id,
            'timestamp': self.timestamp,
            'data': event_data,
            'requires_broadcast': self.requires_broadcast
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        """Create event instance from wire format"""
        event_data = data.get('data', {})
        return cls(
            source_session_id=data.get('source_session_id', 'default'),
            timestamp=data.get('timestamp', time.time()),
            requires_broadcast=data.get('requires_broadcast', True),
            **event_data
        )
```

### 2. User Interaction Events

Define all upstream events (Vue → Python):

```python
# User interaction events (Vue → Python)
@graph_event("nodeCreated", category="user", description="New node created on canvas")
@dataclass
class NodeCreatedEvent(BaseGraphEvent):
    nodeId: str
    position: Dict[str, float]  # {x: float, y: float}

@graph_event("nodePositionChanged", category="user", description="Node position updated")
@dataclass  
class NodePositionChangedEvent(BaseGraphEvent):
    nodeId: str
    position: Dict[str, float]  # {x: float, y: float}

@graph_event("connectionCreated", category="user", description="New connection created")
@dataclass
class ConnectionCreatedEvent(BaseGraphEvent):
    outputNodeId: str
    outletPinId: str
    inputNodeId: str
    inletPinId: str

@graph_event("connectionRemoved", category="user", description="Connection removed")
@dataclass
class ConnectionRemovedEvent(BaseGraphEvent):
    connectionId: str

@graph_event("connectionClicked", category="user", description="Connection clicked")
@dataclass
class ConnectionClickedEvent(BaseGraphEvent):
    connectionId: str

@graph_event("nodeDragStart", category="user", description="Node drag started")
@dataclass
class NodeDragStartEvent(BaseGraphEvent):
    nodeId: str

@graph_event("nodeDragEnd", category="user", description="Node drag ended")
@dataclass
class NodeDragEndEvent(BaseGraphEvent):
    nodeId: str
    positionChanged: bool

@graph_event("selectionChanged", category="user", description="Selection state changed")
@dataclass
class SelectionChangedEvent(BaseGraphEvent):
    selectedNodes: List[str]
    selectedConnections: List[str]

@graph_event("contextMenuCanvas", category="user", description="Canvas context menu triggered")
@dataclass
class ContextMenuCanvasEvent(BaseGraphEvent):
    screenX: float
    screenY: float
    canvasX: float
    canvasY: float

@graph_event("contextMenuNode", category="user", description="Node context menu triggered")
@dataclass
class ContextMenuNodeEvent(BaseGraphEvent):
    screenX: float
    screenY: float
    canvasX: float
    canvasY: float
    nodeId: str

@graph_event("contextMenuConnection", category="user", description="Connection context menu triggered")
@dataclass
class ContextMenuConnectionEvent(BaseGraphEvent):
    screenX: float
    screenY: float
    canvasX: float
    canvasY: float
    connectionId: str
```

### 3. Sync Events

Define all downstream events (Python → Vue):

```python
# Sync events (Python → Vue)
@graph_event("syncNodeAddition", category="sync", description="Sync node addition to UI")
@dataclass
class SyncNodeAdditionEvent(BaseGraphEvent):
    nodeId: str
    position: Dict[str, float]

@graph_event("syncNodeRemoval", category="sync", description="Sync node removal from UI")
@dataclass
class SyncNodeRemovalEvent(BaseGraphEvent):
    nodeId: str

@graph_event("syncNodePosition", category="sync", description="Sync node position to UI")
@dataclass
class SyncNodePositionEvent(BaseGraphEvent):
    nodeId: str
    position: Dict[str, float]

@graph_event("syncConnectionAddition", category="sync", description="Sync connection addition to UI")
@dataclass
class SyncConnectionAdditionEvent(BaseGraphEvent):
    connectionId: str
    outputNodeId: str
    outletPinId: str
    inputNodeId: str
    inletPinId: str

@graph_event("syncConnectionRemoval", category="sync", description="Sync connection removal from UI")
@dataclass
class SyncConnectionRemovalEvent(BaseGraphEvent):
    connectionId: str

@graph_event("syncSelectionState", category="sync", description="Sync selection state to UI")
@dataclass
class SyncSelectionStateEvent(BaseGraphEvent):
    selectedNodes: List[str]
    selectedConnections: List[str]
    action: str = "set"  # "set" or "clear"

@graph_event("syncCanvasClear", category="sync", description="Clear entire canvas")
@dataclass
class SyncCanvasClearEvent(BaseGraphEvent):
    pass

@graph_event("syncAllConnections", category="sync", description="Sync all connections to UI")
@dataclass
class SyncAllConnectionsEvent(BaseGraphEvent):
    connections: List[Dict[str, Any]]
```

## Event Handler Registration System

### Handler Registration Decorator

```python
# event_handlers.py
from typing import Callable, List, Type
from event_definitions import BaseGraphEvent

def handles_event(*event_classes: Type[BaseGraphEvent]):
    """Decorator to register methods as handlers for specific event classes"""
    def decorator(func: Callable):
        func._handles_event_classes = event_classes
        return func
    return decorator
```

## Code Generation System

### Vue Code Generator

```python
# event_generators.py
import dataclasses
from typing import Dict, Any, List
from event_definitions import GRAPH_EVENT_REGISTRY, BaseGraphEvent

class VueEventGenerator:
    @staticmethod
    def generate_event_constants() -> str:
        """Generate Vue/TypeScript constants and creators from Python event registry"""
        
        # Separate events by category
        user_events = {}
        sync_events = {}
        
        for event_type, event_class in GRAPH_EVENT_REGISTRY.items():
            event_info = {
                'type': event_type,
                'class_name': event_class.__name__,
                'description': getattr(event_class, 'description', ''),
                'fields': [f.name for f in dataclasses.fields(event_class) 
                          if f.name not in ['source_session_id', 'timestamp', 'requires_broadcast']]
            }
            
            if getattr(event_class, 'category', 'user') == 'user':
                user_events[event_type] = event_info
            else:
                sync_events[event_type] = event_info
        
        # Generate TypeScript/JavaScript code
        ts_code = f'''
// Auto-generated from Python event definitions
// DO NOT EDIT MANUALLY - Run `python generate_vue_events.py` to update

export interface EventData {{
  [key: string]: any;
}}

export interface GraphEvent {{
  event_type: string;
  source_session_id: string;
  timestamp: number;
  data: EventData;
  requires_broadcast: boolean;
}}

{VueEventGenerator._generate_typescript_interfaces(user_events, sync_events)}

// Event type constants
export const GraphEvents = {{
  UserInteractions: {{
    {VueEventGenerator._format_events_object(user_events)}
  }},
  
  SyncCommands: {{
    {VueEventGenerator._format_events_object(sync_events)}
  }}
}} as const;

// Type-safe event creators
export class EventCreators {{
  {VueEventGenerator._generate_event_creators(user_events)}
}}

// Event validators
export class EventValidators {{
  {VueEventGenerator._generate_event_validators(user_events)}
}}
'''
        return ts_code
    
    @staticmethod
    def _generate_typescript_interfaces(user_events: Dict, sync_events: Dict) -> str:
        """Generate TypeScript interfaces for each event"""
        interfaces = []
        
        for events in [user_events, sync_events]:
            for event_type, info in events.items():
                interface_name = f"{info['class_name']}Data"
                fields = info['fields']
                
                interface = f'''
// {info['description']}
export interface {interface_name} {{'''
                
                # Add fields (simplified type mapping)
                for field in fields:
                    field_type = "any"  # Could be enhanced with more specific types
                    interface += f'''
  {field}: {field_type};'''
                
                interface += '''
}'''
                interfaces.append(interface)
        
        return '\n'.join(interfaces)
    
    @staticmethod
    def _format_events_object(events: Dict) -> str:
        """Format events as JavaScript object properties"""
        lines = []
        for event_type, info in events.items():
            const_name = VueEventGenerator._camel_to_const(event_type)
            lines.append(f"    {const_name}: '{event_type}', // {info['description']}")
        return '\n'.join(lines)
    
    @staticmethod
    def _generate_event_creators(events: Dict) -> str:
        """Generate type-safe event creator methods"""
        methods = []
        for event_type, info in events.items():
            method_name = f"create{info['class_name'].replace('Event', '')}"
            fields_param = ', '.join([f"{field}: any" for field in info['fields']])
            
            method = f'''
  static {method_name}({fields_param}, sessionId: string = 'default'): GraphEvent {{
    return {{
      event_type: '{event_type}',
      source_session_id: sessionId,
      timestamp: Date.now(),
      data: {{ {', '.join(info['fields'])} }},
      requires_broadcast: true
    }};
  }}'''
            methods.append(method)
        
        return '\n'.join(methods)
    
    @staticmethod
    def _generate_event_validators(events: Dict) -> str:
        """Generate event validation methods"""
        methods = []
        for event_type, info in events.items():
            method_name = f"validate{info['class_name'].replace('Event', '')}"
            required_fields = info['fields']
            
            method = f'''
  static {method_name}(data: EventData): boolean {{
    const requiredFields = {str(required_fields).replace("'", '"')};
    return requiredFields.every(field => field in data);
  }}'''
            methods.append(method)
        
        return '\n'.join(methods)
    
    @staticmethod
    def _camel_to_const(camel_str: str) -> str:
        """Convert camelCase to CONST_CASE"""
        import re
        return re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', camel_str).upper()

# Build script
def main():
    """Generate Vue event constants"""
    vue_code = VueEventGenerator.generate_event_constants()
    
    # Create generated directory if it doesn't exist
    import os
    os.makedirs('./vue_components/generated', exist_ok=True)
    
    with open('./vue_components/generated/graph_events.js', 'w') as f:
        f.write(vue_code)
    
    print("Vue event constants generated successfully!")
    print("File: ./vue_components/generated/graph_events.js")

if __name__ == "__main__":
    main()
```

---

## File 1: graph_canvas.vue (Frontend)

### Enhanced Vue Implementation

```vue
<script>
// Import auto-generated constants and creators
import { GraphEvents, EventCreators, EventValidators } from './generated/graph_events.js';

export default {
    name: 'GraphCanvas',
    
    methods: {
        // =============================================================================
        // UNIFIED EVENT EMISSION SYSTEM
        // =============================================================================
        
        emitCanvasEvent(event) {
            /**
             * Unified event emitter using generated event objects
             */
            console.log(`🔄 Vue→Python Event: ${event.event_type}`, event.data);
            this.$emit('canvasEvent', event);
        },
        
        // =============================================================================
        // UNIFIED SYNC EVENT HANDLER  
        // =============================================================================
        
        handleSyncEvent(event) {
            /**
             * Unified sync event handler using generated constants
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
        // USER INTERACTION HANDLERS (Using type-safe event creators)
        // =============================================================================
        
        handleNodeCreated(nodeId, position) {
            const event = EventCreators.createNodeCreated(nodeId, position, this.sessionId);
            this.emitCanvasEvent(event);
        },
        
        handleNodePositionChange(nodeId, x, y, positionChanged) {
            if (positionChanged) {
                const event = EventCreators.createNodePositionChanged(
                    nodeId, 
                    { x, y }, 
                    this.sessionId
                );
                this.emitCanvasEvent(event);
            }
        },
        
        handleConnectionCreated(startNodeId, startPort, endNodeId, endPort) {
            const event = EventCreators.createConnectionCreated(
                startNodeId,
                startPort,
                endNodeId,
                endPort,
                this.sessionId
            );
            this.emitCanvasEvent(event);
        },
        
        handleConnectionRemoved(connectionId) {
            const event = EventCreators.createConnectionRemoved(connectionId, this.sessionId);
            this.emitCanvasEvent(event);
        },
        
        handleConnectionClicked(connectionId) {
            const event = EventCreators.createConnectionClicked(connectionId, this.sessionId);
            this.emitCanvasEvent(event);
        },
        
        handleNodeDragStart(nodeId) {
            const event = EventCreators.createNodeDragStart(nodeId, this.sessionId);
            this.emitCanvasEvent(event);
        },
        
        handleNodeDragEnd(nodeId, positionChanged) {
            const event = EventCreators.createNodeDragEnd(nodeId, positionChanged, this.sessionId);
            this.emitCanvasEvent(event);
        },
        
        handleSelectionChanged() {
            const event = EventCreators.createSelectionChanged(
                Array.from(this.selectedNodes),
                Array.from(this.selectedConnections),
                this.sessionId
            );
            this.emitCanvasEvent(event);
        },
        
        handleContextMenu(event, targetType, targetId = null) {
            event.preventDefault();
            
            const baseData = {
                screenX: event.clientX,
                screenY: event.clientY,
                canvasX: event.offsetX,
                canvasY: event.offsetY
            };
            
            let contextEvent;
            if (targetType === 'canvas') {
                contextEvent = EventCreators.createContextMenuCanvas(
                    baseData.screenX, baseData.screenY,
                    baseData.canvasX, baseData.canvasY,
                    this.sessionId
                );
            } else if (targetType === 'node') {
                contextEvent = EventCreators.createContextMenuNode(
                    baseData.screenX, baseData.screenY,
                    baseData.canvasX, baseData.canvasY,
                    targetId,
                    this.sessionId
                );
            } else if (targetType === 'connection') {
                contextEvent = EventCreators.createContextMenuConnection(
                    baseData.screenX, baseData.screenY,
                    baseData.canvasX, baseData.canvasY,
                    targetId,
                    this.sessionId
                );
            }
            
            this.emitCanvasEvent(contextEvent);
        },
        
        // =============================================================================
        // SYNC EVENT HANDLERS
        // =============================================================================
        
        handleSyncNodeAddition(data) {
            const { nodeId, position } = data;
            this.$nextTick(() => {
                const nodeElement = document.getElementById(nodeId);
                if (nodeElement) {
                    nodeElement.style.left = `${position.x}px`;
                    nodeElement.style.top = `${position.y}px`;
                    console.log(`✅ Synced node addition: ${nodeId}`);
                }
            });
        },
        
        handleSyncNodeRemoval(data) {
            const { nodeId } = data;
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
                this.clearSelection();
                selectedNodes.forEach(nodeId => this.selectNode(nodeId, true));
                selectedConnections.forEach(connId => this.selectConnection(connId, true));
            }
            console.log(`✅ Synced selection state`);
        },
        
        handleSyncAllConnections(data) {
            const { connections } = data;
            this.connections.splice(0, this.connections.length, ...connections);
            console.log(`✅ Synced all connections: ${connections.length} connections`);
        },
        
        handleSyncCanvasClear(data) {
            this.clearSelection();
            this.connections.splice(0);
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

---

## File 2: graph_canvas_vue.py (Python Wrapper)

### Enhanced NiceGUI Wrapper

```python
from typing import Optional, Callable
from nicegui import ui
from event_definitions import BaseGraphEvent

class GraphCanvasVue(ui.element, component='graph_canvas.vue'):
    """Vue-based graph canvas component with enhanced event handling."""
    
    def __init__(self, 
                 on_canvas_event: Optional[Callable[[BaseGraphEvent], None]] = None,
                 zoom_container=None,
                 canvas_width: int = 8000, 
                 canvas_height: int = 8000):
        super().__init__()
        
        # Single unified event callback
        self._on_canvas_event = on_canvas_event
        
        # Store zoom container reference
        self.zoom_container = zoom_container
        
        # Props for Vue component  
        self._props['canvasWidth'] = canvas_width
        self._props['canvasHeight'] = canvas_height
        self._props['connections'] = []
        self._props['data-graph_canvas'] = True
        
        # Register single event handler
        self.on('canvasEvent', self._handle_canvas_event)
    
    def _handle_canvas_event(self, event_data):
        """
        Unified canvas event handler - routes to GraphCanvasManager
        """
        if self._on_canvas_event and hasattr(event_data, 'args'):
            event = event_data.args
            event_type = event.get('event_type')
            
            # Log for debugging
            print(f"🔄 Vue→Python Event: {event_type} | Data: {event.get('data', {})}")
            
            # Create event instance from registry
            if event_type in GRAPH_EVENT_REGISTRY:
                event_class = GRAPH_EVENT_REGISTRY[event_type]
                try:
                    event_instance = event_class.from_dict(event)
                    self._on_canvas_event(event_instance)
                except Exception as e:
                    print(f"Error creating event instance for {event_type}: {e}")
                    # Fallback to raw dict
                    self._on_canvas_event(event)
            else:
                print(f"Unknown event type: {event_type}")
                self._on_canvas_event(event)
    
    def emit_sync_event(self, event: BaseGraphEvent):
        """
        Send sync event to Vue component
        """
        event_dict = event.to_dict()
        event_type = event_dict.get('event_type')
        data = event_dict.get('data', {})
        
        print(f"🔄 Python→Vue Event: {event_type} | Data: {data}")
        
        # Send to Vue component
        self.run_method('handleSyncEvent', event_dict)
    
    def update_connections_prop(self, connections):
        """Update connections prop for Vue component"""
        self._props['connections'] = connections
```

---

## File 3: graph_canvas_manager.py (Business Logic)

### Enhanced Manager with Auto-Registration

```python
from typing import Dict, List, Callable, Type
import time
from event_definitions import *
from event_handlers import handles_event
import inspect

class GraphCanvasManager:
    """Graph canvas manager with class-based event system."""
    
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
        
        # Event handling system
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
                on_create_node=self._handle_context_create_node,
                on_duplicate_node=self._handle_context_duplicate_node,
                on_copy_node=self._handle_context_copy_node,
                on_delete_node=self._handle_context_delete_node,
                on_inspect_connection=self._handle_context_inspect_connection,
                on_delete_connection=self._handle_context_delete_connection
            )
    
    def _handle_canvas_event(self, event):
        """
        Unified canvas event router using auto-registered handlers
        """
        if isinstance(event, BaseGraphEvent):
            event_type = event.event_type
            handler = self._event_handlers.get(event_type)
            
            if handler:
                # Determine parameter signature and call appropriately
                sig = inspect.signature(handler)
                param_count = len(sig.parameters) - 1  # Exclude 'self'
                
                if param_count == 1:
                    handler(event)
                else:
                    # Legacy support - extract data
                    handler(event.to_dict())
            else:
                print(f"No handler found for event type: {event_type}")
        else:
            # Handle legacy dict format
            event_type = event.get('event_type')
            handler = self._event_handlers.get(event_type)
            if handler:
                handler(event)
            else:
                print(f"No handler found for event type: {event_type}")
    
    # =============================================================================
    # EVENT HANDLERS (Auto-registered via decorators)
    # =============================================================================
    
    @handles_event(NodeCreatedEvent)
    def process_node_creation(self, event: NodeCreatedEvent):
        """Handle node creation requests"""
        try:
            print(f"Creating node: {event.nodeId} at ({event.position['x']}, {event.position['y']})")
            
            # Business logic for node creation
            # ... implement node creation ...
            
            # Broadcast to other sessions
            if event.requires_broadcast:
                sync_event = SyncNodeAdditionEvent(
                    nodeId=event.nodeId,
                    position=event.position
                )
                self._broadcast_sync_event(sync_event, exclude_session=event.source_session_id)
                
        except Exception as e:
            print(f"Node creation failed: {e}")
    
    @handles_event(NodePositionChangedEvent)
    def process_node_position_change(self, event: NodePositionChangedEvent):
        """Handle node position updates"""
        try:
            print(f"Updating node position: {event.nodeId} to ({event.position['x']}, {event.position['y']})")
            
            # Update graph state
            # ... implement position update logic ...
            
            # Broadcast to other sessions
            if event.requires_broadcast:
                sync_event = SyncNodePositionEvent(
                    nodeId=event.nodeId,
                    position=event.position
                )
                self._broadcast_sync_event(sync_event, exclude_session=event.source_session_id)
                
        except Exception as e:
            print(f"Node position update failed: {e}")
    
    @handles_event(ConnectionCreatedEvent)
    def process_connection_creation(self, event: ConnectionCreatedEvent):
        """Handle connection creation"""
        try:
            print(f"Creating connection: {event.outputNodeId}:{event.outletPinId} -> {event.inputNodeId}:{event.inletPinId}")
            
            # Create edge in graph
            edge = Edge(
                edge_type=EdgeType.DATA,
                output_node_id=event.outputNodeId,
                outlet_pin_id=event.outletPinId,
                input_node_id=event.inputNodeId,
                inlet_pin_id=event.inletPinId
            )
            
            # Add to graph and get connection ID
            connection_id = self.graph.add_edge(edge)
            
            # Broadcast to other sessions
            if event.requires_broadcast:
                sync_event = SyncConnectionAdditionEvent(
                    connectionId=connection_id,
                    outputNodeId=event.outputNodeId,
                    outletPinId=event.outletPinId,
                    inputNodeId=event.inputNodeId,
                    inletPinId=event.inletPinId
                )
                self._broadcast_sync_event(sync_event, exclude_session=event.source_session_id)
                
        except Exception as e:
            print(f"Connection creation failed: {e}")
    
    @handles_event(ConnectionRemovedEvent)
    def process_connection_removal(self, event: ConnectionRemovedEvent):
        """Handle connection removal"""
        try:
            print(f"Removing connection: {event.connectionId}")
            
            # Remove from graph
            self.graph.remove_edge_by_id(event.connectionId)
            
            # Broadcast to other sessions
            if event.requires_broadcast:
                sync_event = SyncConnectionRemovalEvent(
                    connectionId=event.connectionId
                )
                self._broadcast_sync_event(sync_event, exclude_session=event.source_session_id)
                
        except Exception as e:
            print(f"Connection removal failed: {e}")
    
    @handles_event(ConnectionClickedEvent)
    def process_connection_click(self, event: ConnectionClickedEvent):
        """Handle connection click events"""
        print(f"Connection clicked: {event.connectionId}")
        # Implement connection click logic
        pass
    
    @handles_event(NodeDragStartEvent)
    def process_node_drag_start(self, event: NodeDragStartEvent):
        """Handle node drag start"""
        print(f"Node drag started: {event.nodeId}")
        # Implement drag start logic
        pass
    
    @handles_event(NodeDragEndEvent)
    def process_node_drag_end(self, event: NodeDragEndEvent):
        """Handle node drag end"""
        print(f"Node drag ended: {event.nodeId}, position changed: {event.positionChanged}")
        # Implement drag end logic
        pass
    
    @handles_event(SelectionChangedEvent)
    def process_selection_change(self, event: SelectionChangedEvent):
        """Handle selection changes"""
        print(f"Selection changed: nodes={event.selectedNodes}, connections={event.selectedConnections}")
        
        # Broadcast to other sessions
        if event.requires_broadcast:
            sync_event = SyncSelectionStateEvent(
                selectedNodes=event.selectedNodes,
                selectedConnections=event.selectedConnections,
                action="set"
            )
            self._broadcast_sync_event(sync_event, exclude_session=event.source_session_id)
    
    @handles_event(ContextMenuCanvasEvent, ContextMenuNodeEvent, ContextMenuConnectionEvent)
    def process_context_menu(self, event):
        """Handle context menu events"""
        if isinstance(event, ContextMenuCanvasEvent):
            print(f"Canvas context menu at ({event.screenX}, {event.screenY})")
            self.context_menu.show_canvas_menu(event.screenX, event.screenY)
            
        elif isinstance(event, ContextMenuNodeEvent):
            print(f"Node context menu for {event.nodeId} at ({event.screenX}, {event.screenY})")
            self.context_menu.show_node_menu(event.screenX, event.screenY, event.nodeId)
            
        elif isinstance(event, ContextMenuConnectionEvent):
            print(f"Connection context menu for {event.connectionId} at ({event.screenX}, {event.screenY})")
            self.context_menu.show_connection_menu(event.screenX, event.screenY, event.connectionId)
    
    # =============================================================================
    # SYNC EVENT BROADCASTING
    # =============================================================================
    
    def _broadcast_sync_event(self, sync_event: BaseGraphEvent, exclude_session: str = None):
        """Broadcast sync event to all other sessions"""
        # Implementation depends on your session management system
        # This is a placeholder for the actual broadcasting logic
        
        for session_id, session_manager in self.get_all_sessions().items():
            if session_id != exclude_session:
                session_manager.canvas_vue.emit_sync_event(sync_event)
    
    def get_all_sessions(self):
        """Get all active sessions - implement based on your session management"""
        # Placeholder - replace with actual session management logic
        return {}
    
    # =============================================================================
    # PUBLIC API METHODS
    # =============================================================================
    
    def sync_all_connections_to_session(self, session_id: str):
        """Sync all current connections to a specific session"""
        connections_data = []
        for edge in self.graph.edges:
            connections_data.append({
                'connectionId': edge.id,
                'outputNodeId': edge.output_node_id,
                'outletPinId': edge.outlet_pin_id,
                'inputNodeId': edge.input_node_id,
                'inletPinId': edge.inlet_pin_id
            })
        
        sync_event = SyncAllConnectionsEvent(connections=connections_data)
        
        # Send to specific session
        session_manager = self.get_session(session_id)
        if session_manager:
            session_manager.canvas_vue.emit_sync_event(sync_event)
    
    def clear_canvas_for_all_sessions(self):
        """Clear canvas for all sessions"""
        # Clear internal state
        self.graph.clear()
        
        # Broadcast clear event
        sync_event = SyncCanvasClearEvent()
        self._broadcast_sync_event(sync_event)
    
---

## Migration Strategy

### Phase 1: Setup Event System Foundation

1. **Create Event Definitions Module**
   ```bash
   # Create new files
   touch event_definitions.py
   touch event_handlers.py
   touch event_generators.py
   touch generate_vue_events.py
   ```

2. **Define All Event Classes**
   - Copy event definitions from this document into `event_definitions.py`
   - Ensure all current event types are covered
   - Add any missing event types specific to your implementation

3. **Generate Vue Constants**
   ```bash
   python generate_vue_events.py
   ```
   - Creates `./vue_components/generated/graph_events.js`
   - Update Vue component imports to use generated constants

### Phase 2: Convert Event Handlers

1. **Update GraphCanvasManager**
   - Add auto-registration system (`_auto_register_event_handlers`)
   - Convert existing handler methods to use `@handles_event` decorators
   - Replace manual event routing with unified `_handle_canvas_event`

2. **Convert Handler Methods**
   ```python
   # Old approach
   def _handle_vue_node_position_changed(self, event_data):
       node_id = event_data['data']['nodeId']
       # ... logic

   # New approach  
   @handles_event(NodePositionChangedEvent)
   def process_node_position_change(self, event: NodePositionChangedEvent):
       node_id = event.nodeId
       # ... logic
   ```

3. **Update GraphCanvasVue**
   - Replace multiple callback parameters with single `on_canvas_event`
   - Add `emit_sync_event` method for downstream events
   - Remove individual method calls in favor of unified sync system

### Phase 3: Update Vue Component

1. **Import Generated Constants**
   ```javascript
   // Replace manual constants
   import { GraphEvents, EventCreators } from './generated/graph_events.js';
   ```

2. **Convert Event Emissions**
   ```javascript
   // Old approach
   this.$emit('canvasEvent', {
       event_type: 'nodePositionChanged',
       data: { nodeId, position: {x, y} }
   });

   // New approach
   const event = EventCreators.createNodePositionChanged(nodeId, {x, y}, this.sessionId);
   this.emitCanvasEvent(event);
   ```

3. **Update Event Handlers**
   - Use generated constants instead of string literals
   - Implement unified `handleSyncEvent` method
   - Remove individual sync method calls

### Phase 4: Integration and Testing

1. **Build Integration**
   - Add code generation to build process
   - Ensure `python generate_vue_events.py` runs before Vue compilation
   - Update development workflow documentation

2. **Validation**
   - Test all event flows: Vue → Python → Vue
   - Verify session broadcasting works correctly
   - Confirm all existing functionality preserved

3. **Cleanup**
   - Remove old event constant definitions
   - Delete unused individual callback methods
   - Update documentation and examples

### Key Migration Benefits

1. **Type Safety**: Event class references prevent typos and provide IDE support
2. **Maintainability**: Single source of truth for all event definitions
3. **Consistency**: Automatic synchronization between Python and Vue
4. **Debugging**: Enhanced logging and validation capabilities
5. **Scalability**: Easy to add new events without manual constant management

### Development Workflow

```bash
# 1. Define new event in Python
@graph_event("newFeature", category="user")
@dataclass
class NewFeatureEvent(BaseGraphEvent):
    featureId: str
    config: Dict[str, Any]

# 2. Add handler
@handles_event(NewFeatureEvent) 
def process_new_feature(self, event: NewFeatureEvent):
    # Implementation

# 3. Generate Vue constants
python generate_vue_events.py

# 4. Use in Vue (auto-completion available)
const event = EventCreators.createNewFeature(featureId, config, this.sessionId);
this.emitCanvasEvent(event);
```

This migration transforms your event system from manual string-based routing to a type-safe, automatically synchronized architecture that scales efficiently as your application grows.