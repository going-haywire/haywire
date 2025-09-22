"""
Event definitions for the enhanced graph canvas event system.

This module provides:
- Class-based event definitions using dataclasses
- Type-safe event registration and serialization
- Single source of truth for all event types
- Automatic code generation support
"""

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
class GraphEventMetadata:
    source_session_id: str = "default"
    timestamp: float = field(default_factory=time.time)
    requires_broadcast: bool = True

@dataclass
class BaseGraphEvent:
    """Base class without default fields"""
    
    def to_dict(self, metadata: GraphEventMetadata = None) -> Dict[str, Any]:
        if metadata is None:
            metadata = GraphEventMetadata()
            
        event_data = {}
        for field in dataclasses.fields(self):
            event_data[field.name] = getattr(self, field.name)
        
        return {
            'event_type': self.event_type,
            'source_session_id': metadata.source_session_id,
            'timestamp': metadata.timestamp,
            'data': event_data,
            'requires_broadcast': metadata.requires_broadcast
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        """Create event instance from wire format"""
        event_data = data.get('data', {})
        # Only pass the actual event fields, not metadata
        return cls(**event_data)
    
    def get_metadata_from_dict(self, data: Dict[str, Any]) -> GraphEventMetadata:
        """Extract metadata from wire format"""
        return GraphEventMetadata(
            source_session_id=data.get('source_session_id', 'default'),
            timestamp=data.get('timestamp', time.time()),
            requires_broadcast=data.get('requires_broadcast', True)
        )
    
# =============================================================================
# USER INTERACTION EVENTS (Vue → Python)
# =============================================================================

@graph_event("nodeCreateRequest", category="user", description="Request to create node from context menu")
@dataclass
class NodeCreateRequestEvent(BaseGraphEvent):
    nodeType: str
    position: Dict[str, float]  # {x: float, y: float}

@graph_event("nodeRemoveRequest", category="user", description="Request to remove node from context menu")
@dataclass
class NodeRemoveRequestEvent(BaseGraphEvent):
    nodeId: str

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

# =============================================================================
# SYNC EVENTS (Python → Vue)
# =============================================================================

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

@graph_event("syncNodeSelection", category="sync", description="Select/deselect individual node")
@dataclass
class SyncNodeSelectionEvent(BaseGraphEvent):
    nodeId: str
    selected: bool
    multiSelect: bool = False

@graph_event("syncConnectionSelection", category="sync", description="Select/deselect individual connection")
@dataclass
class SyncConnectionSelectionEvent(BaseGraphEvent):
    connectionId: str
    selected: bool
    multiSelect: bool = False

@graph_event("syncClearAllSelections", category="sync", description="Clear all selections")
@dataclass
class SyncClearAllSelectionsEvent(BaseGraphEvent):
    pass

@graph_event("syncNodeObserverAdd", category="sync", description="Add node observer")
@dataclass
class SyncNodeObserverAddEvent(BaseGraphEvent):
    nodeId: str

@graph_event("syncNodeObserverRemove", category="sync", description="Remove node observer")
@dataclass
class SyncNodeObserverRemoveEvent(BaseGraphEvent):
    nodeId: str

@graph_event("syncConnectionsUpdate", category="sync", description="Update connections for node")
@dataclass
class SyncConnectionsUpdateEvent(BaseGraphEvent):
    nodeId: str