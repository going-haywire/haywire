"""
UIEdge - Manager class for edge UI lifecycle with hot reload support

This class manages the relationship between an EdgeWrapper and its visual
representation, following the same pattern as UINode.

Features:
- Subscribes to EdgeWrapper lifecycle events
- Automatically updates visual state when adapters are hot-reloaded
- Emits sync events to Vue component for visual updates
- Provides detailed information via context menu
"""

import logging
from dataclasses import dataclass
from typing import Callable, Optional

from haywire.core.edge.edge_wrapper import EdgeWrapper
from haywire.core.graph.types import ChangeReason
from haybale_studio.editors.graph_canvas.event_definitions import SyncEdgeAdditionEvent, BaseGraphEvent

logger = logging.getLogger(__name__)


@dataclass
class EdgeVisualState:
    """
    Visual state for connection rendering.

    This determines how the connection appears in the UI.
    All visual feedback is conveyed through these properties only.
    """

    edge_id: str

    # Visual properties
    stroke_color: str
    stroke_width: int
    stroke_dasharray: str  # "" for solid, "5,5" for dashed, "2,4" for dotted
    opacity: float

    # State flags (used to derive visual properties)
    is_valid: bool
    has_warning: bool

    def __eq__(self, other) -> bool:
        """Compare visual states to detect changes"""
        if not isinstance(other, EdgeVisualState):
            return False
        return (
            self.stroke_color == other.stroke_color
            and self.stroke_width == other.stroke_width
            and self.stroke_dasharray == other.stroke_dasharray
            and self.opacity == other.opacity
        )


class UIEdge:
    """
    Manages the lifecycle and visual representation of an EdgeWrapper.

    This class:
    - Holds reference to EdgeWrapper
    - Uses sync events for reliable state updates
    - Subscribes to EdgeWrapper for hot reload support
    - Has no direct SVG manipulation (clean separation)
    - Provides metrics and info for context menu
    """

    def __init__(self, wrapper: EdgeWrapper, sync_event_emitter: Callable[[BaseGraphEvent], None]):
        """
        Initialize UIEdge with wrapper and event emitter.

        Args:
            wrapper: EdgeWrapper managing the edge logic
            sync_event_emitter: Function to emit sync events to Vue
        """
        self.wrapper: EdgeWrapper = wrapper
        self.sync_event_emitter: Callable[[BaseGraphEvent], None] = sync_event_emitter

        # Generate unique ID for this UIEdge
        self.ui_edge_id = wrapper.edge_id

        # Track current visual state to detect changes
        self._current_visual_state: Optional[EdgeVisualState] = None

        # Perform initial sync to UI
        self.refresh(ChangeReason.EDGE_ADDED)

    def _calculate_visual_state(self) -> EdgeVisualState:
        """
        Calculate visual state from EdgeWrapper state.

        Visual States:
        1. VALID (default): Use gradient ('auto'), full opacity
        2. WARNING (chain changed): Orange color, full opacity
        3. INVALID (error): Red dashed line, reduced opacity

        Returns:
            EdgeVisualState with appropriate styling
        """
        # State: INVALID (highest priority)
        if not self.wrapper.is_valid():
            return EdgeVisualState(
                edge_id=self.wrapper.edge_id,
                stroke_color="#EF4444",  # Red
                stroke_width=2,
                stroke_dasharray="5,5",  # Dashed
                opacity=0.7,
                is_valid=False,
                has_warning=False,
            )

        # State: WARNING (adapter chain changed)
        if self.wrapper.state.has_warning():
            return EdgeVisualState(
                edge_id=self.wrapper.edge_id,
                stroke_color="auto",  # Orange/Amber
                stroke_width=2,
                stroke_dasharray="2,2,2,2,2,5,5,5,5,5,5,5",  # Solid
                opacity=1.0,
                is_valid=True,
                has_warning=True,
            )

        # State: VALID (default) - use 'auto' for gradient
        return EdgeVisualState(
            edge_id=self.wrapper.edge_id,
            stroke_color="auto",  # Use gradient from pins
            stroke_width=2,
            stroke_dasharray=self.calculate_dasharray(len(self.wrapper.edge.chain_adapter_keys)),  # Solid
            opacity=1.0,
            is_valid=True,
            has_warning=False,
        )

    def calculate_dasharray(self, chain_length: int) -> str:
        if chain_length == 0:
            return ""
        return "40,2" + ",2,2" * (chain_length)

    def refresh(self, reason: ChangeReason):
        """
        Synchronize current EdgeWrapper state to Vue component.

        Emits SYNC_EDGE_ADDITION which handles both creation and updates.
        Only updates when visual properties actually change.
        """
        new_state = self._calculate_visual_state()

        # Skip if visual state hasn't changed
        if self._current_visual_state == new_state:
            return

        self._current_visual_state = new_state

        # Get node/pin IDs from wrapper
        edge = self.wrapper

        # Emit sync event to Vue (handles both add and update)
        event = SyncEdgeAdditionEvent(
            edge_id=new_state.edge_id,
            sourceNodeId=edge.source_node_id,
            outletPinId=edge.outlet_port_id,
            sinkNodeId=edge.sink_node_id,
            inletPinId=edge.inlet_port_id,
            outletPinFallback=edge.outletPinFallback,
            inletPinFallback=edge.inletPinFallback,
            isValid=new_state.is_valid,
            hasWarning=new_state.has_warning,
            strokeColor=new_state.stroke_color,
            strokeWidth=new_state.stroke_width,
            strokeDasharray=new_state.stroke_dasharray,
            opacity=new_state.opacity,
        )

        self.sync_event_emitter(event)

        logger.debug(
            f"🔗 UIEdge synced: {new_state.edge_id} -> "
            f"color={new_state.stroke_color}, "
            f"valid={new_state.is_valid}, "
            f"warning={new_state.has_warning}"
        )

    def cleanup(self):
        """
        Clean up UIEdge resources.

        Callers (visual_layer) pop the UIEdge from ``edge_paths`` before
        calling cleanup, so no external reader can fetch this instance
        afterwards. The wrapper reference is dropped naturally when this
        UIEdge itself is garbage-collected.
        """
        self._current_visual_state = None
        logger.debug(f"🔗 UIEdge cleaned up: {self.ui_edge_id}")

    def is_valid(self) -> bool:
        """Check if connection is in valid state"""
        return self.wrapper.is_valid()

    def get_edge_id(self) -> str:
        """Get the edge ID"""
        return self.wrapper.edge_id
