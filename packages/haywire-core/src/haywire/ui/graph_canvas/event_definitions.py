"""
Event definitions for the enhanced graph canvas event system - CONSOLIDATED VERSION

This module provides:
- Class-based event definitions using dataclasses
- Type-safe event registration and serialization
- Single source of truth for all event types
- Automatic code generation support
- Consolidated drag, selection, and removal events
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
        for datafield in dataclasses.fields(self):
            event_data[datafield.name] = getattr(self, datafield.name)

        return {
            "event_type": self.event_type,
            "source_session_id": metadata.source_session_id,
            "timestamp": metadata.timestamp,
            "data": event_data,
            "requires_broadcast": metadata.requires_broadcast,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        """Create event instance from wire format"""
        event_data = data.get("data", {})
        # Only pass the actual event fields, not metadata
        return cls(**event_data)

    def get_metadata_from_dict(self, data: Dict[str, Any]) -> GraphEventMetadata:
        """Extract metadata from wire format"""
        return GraphEventMetadata(
            source_session_id=data.get("source_session_id", "default"),
            timestamp=data.get("timestamp", time.time()),
            requires_broadcast=data.get("requires_broadcast", True),
        )


# =============================================================================
# CONSOLIDATED USER INTERACTION EVENTS (Vue → Python)
# =============================================================================


@graph_event("userDragStart", category="user", description="User started dragging nodes")
@dataclass
class UserDragStartEvent(BaseGraphEvent):
    nodes: List[str]  # List of node IDs being dragged


@graph_event("userDragUpdate", category="user", description="User is dragging nodes")
@dataclass
class UserDragUpdateEvent(BaseGraphEvent):
    nodes: List[str]  # List of node IDs being dragged
    deltaX: float
    deltaY: float


@graph_event("userDragEnd", category="user", description="User finished dragging nodes")
@dataclass
class UserDragEndEvent(BaseGraphEvent):
    nodes: List[str]  # List of node IDs that were dragged


@graph_event("nodeCreateRequest", category="user", description="Request to create node from context menu")
@dataclass
class NodeCreateRequestEvent(BaseGraphEvent):
    registryKey: str
    position: Dict[str, float]  # {x: float, y: float}


@graph_event("edgeCreated", category="user", description="New connection created")
@dataclass
class EdgeCreatedEvent(BaseGraphEvent):
    sourceNodeId: str
    outletPinId: str
    sinkNodeId: str
    inletPinId: str


@graph_event("edgeClicked", category="user", description="Connection clicked")
@dataclass
class EdgeClickedEvent(BaseGraphEvent):
    edge_id: str


@graph_event("elementRedraw", category="user", description="redraw selected element")
@dataclass
class ElementRedrawEvent(BaseGraphEvent):
    nodes: List[str]
    edges: List[str]


@graph_event("elementReset", category="user", description="reset selected element")
@dataclass
class ElementResetEvent(BaseGraphEvent):
    nodes: List[str]
    edges: List[str]


@graph_event("elementRevalidate", category="user", description="revalidate selected element")
@dataclass
class ElementRevalidateEvent(BaseGraphEvent):
    nodes: List[str]
    edges: List[str]


@graph_event("selectionChanged", category="user", description="Selection state changed")
@dataclass
class SelectionChangedEvent(BaseGraphEvent):
    selectedNodes: List[str]
    selectedEdges: List[str]


@graph_event("userRemove", category="user", description="User wants to remove elements")
@dataclass
class UserRemoveEvent(BaseGraphEvent):
    nodes: List[str]
    edges: List[str]


@graph_event("userCopySelected", category="user", description="Copy selected elements to clipboard")
@dataclass
class UserCopySelectedEvent(BaseGraphEvent):
    selectedNodes: List[str]
    selectedEdges: List[str]


@graph_event("contextMenuCanvas", category="user", description="Canvas context menu triggered")
@dataclass
class ContextMenuCanvasEvent(BaseGraphEvent):
    screenX: float
    screenY: float
    canvasX: float
    canvasY: float
    # Non-empty when right-clicked while a connection drag was in progress.
    pendingPinId: str = ""
    pendingNodeId: str = ""
    pendingPinDir: str = ""  # 'inlet' | 'outlet' | ''
    pendingFlowType: str = ""  # 'data' | 'control' | 'callback' | ''
    pendingDataType: str = ""  # data-type registry key or ''


@graph_event("contextMenuNode", category="user", description="Node context menu triggered")
@dataclass
class ContextMenuNodeEvent(BaseGraphEvent):
    screenX: float
    screenY: float
    canvasX: float
    canvasY: float
    nodeId: str


@graph_event("contextMenuEdge", category="user", description="Connection context menu triggered")
@dataclass
class ContextMenuEdgeEvent(BaseGraphEvent):
    screenX: float
    screenY: float
    canvasX: float
    canvasY: float
    edge_id: str
    # True if the right-click was closer to the inlet (sink) end of the edge.
    atSinkEnd: bool = False


@graph_event(
    "contextMenuSelected", category="user", description="Context menu triggered on selected elements"
)
@dataclass
class ContextMenuSelectedEvent(BaseGraphEvent):
    screenX: float
    screenY: float
    canvasX: float
    canvasY: float
    selectedNodes: List[str]
    selectedEdges: List[str]


@graph_event(
    "contextMenuCustom",
    category="user",
    description="Custom-scope context menu triggered via data-hw-custom-menu-scope attribute",
)
@dataclass
class ContextMenuCustomEvent(BaseGraphEvent):
    screenX: float
    screenY: float
    canvasX: float
    canvasY: float
    nodeId: str
    scope: str


@graph_event(
    "contextMenuPort",
    category="user",
    description="Port context menu triggered via data-hw-port-menu-scope attribute",
)
@dataclass
class ContextMenuPortEvent(BaseGraphEvent):
    screenX: float
    screenY: float
    canvasX: float
    canvasY: float
    nodeId: str
    portId: str
    scope: str


@graph_event("userPasteClipboard", category="user", description="Paste clipboard contents")
@dataclass
class UserPasteClipboardEvent(BaseGraphEvent):
    canvasX: float
    canvasY: float


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


@graph_event(
    "syncEdgeAddition",
    category="sync",
    description="Sync connection addition/update to UI with visual properties",
)
@dataclass
class SyncEdgeAdditionEvent(BaseGraphEvent):
    """Sync edge to UI - handles both creation and updates.

    Visual properties:
    - strokeColor: 'auto' uses gradient, otherwise solid color
    - strokeWidth: Line thickness
    - strokeDasharray: Dash pattern ('' for solid)
    - opacity: Transparency (0.0-1.0)
    - isValid: Connection validity state
    - hasWarning: Warning indicator
    """

    edge_id: str
    sourceNodeId: str
    outletPinId: str
    sinkNodeId: str
    inletPinId: str
    outletPinFallback: str
    inletPinFallback: str
    isValid: bool = True
    hasWarning: bool = False
    strokeColor: str = "auto"  # 'auto' = use gradient, else solid color
    strokeWidth: int = 2
    strokeDasharray: str = ""
    opacity: float = 1.0


@graph_event("syncEdgeRemoval", category="sync", description="Sync connection removal from UI")
@dataclass
class SyncEdgeRemovalEvent(BaseGraphEvent):
    edge_id: str


@graph_event("syncSelections", category="sync", description="Sync selection state to UI")
@dataclass
class SyncSelectionsEvent(BaseGraphEvent):
    nodes: List[str]
    edges: List[str]


@graph_event("syncCanvasClear", category="sync", description="Clear entire canvas")
@dataclass
class SyncCanvasClearEvent(BaseGraphEvent):
    pass


@graph_event("syncAllEdges", category="sync", description="Sync all connections to UI")
@dataclass
class SyncAllEdgesEvent(BaseGraphEvent):
    edges: List[Dict[str, Any]]


@graph_event(
    "syncNodeRedraw",
    category="sync",
    description="Node DOM was rebuilt — re-attach observer and redraw edges",
)
@dataclass
class SyncNodeRedrawEvent(BaseGraphEvent):
    nodeId: str


@graph_event("syncEdgesUpdate", category="sync", description="Update connections for node")
@dataclass
class SyncEdgesUpdateEvent(BaseGraphEvent):
    nodeId: str


@graph_event(
    "syncStartReconnect",
    category="sync",
    description="Remove an edge and start a new connection drag from the anchor pin",
)
@dataclass
class SyncStartReconnectEvent(BaseGraphEvent):
    edge_id: str
    anchorNodeId: str
    anchorPinId: str


@graph_event(
    "syncPlayPendingConnection",
    category="sync",
    description="Resume a paused pending connection drag (context menu dismissed without action)",
)
@dataclass
class SyncPlayPendingConnectionEvent(BaseGraphEvent):
    pass
