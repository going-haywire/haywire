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
from typing import Any, Callable, Optional, List

from haywire.core.edge.edge_wrapper import EdgeWrapper
from haywire.core.registry.lifecycle_event import (
    LifeCycleEvent,
    LifeCycleEventType
)
from haywire.ui.editor.event_definitions import (
    SyncConnectionAdditionEvent,
    BaseGraphEvent
)


@dataclass
class EdgeVisualState:
    """
    Visual state for connection rendering.
    
    This determines how the connection appears in the UI.
    All visual feedback is conveyed through these properties only.
    """
    connection_uuid: str
    
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
            self.stroke_color == other.stroke_color and
            self.stroke_width == other.stroke_width and
            self.stroke_dasharray == other.stroke_dasharray and
            self.opacity == other.opacity
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

    def __init__(
        self,
        wrapper: EdgeWrapper,
        sync_event_emitter: Callable[[BaseGraphEvent], None]
    ):
        """
        Initialize UIEdge with wrapper and event emitter.
        
        Args:
            wrapper: EdgeWrapper managing the edge logic
            sync_event_emitter: Function to emit sync events to Vue
        """
        self.wrapper: EdgeWrapper = wrapper
        self.sync_event_emitter = sync_event_emitter
        
        # Generate unique ID for this UIEdge
        self.ui_edge_id = wrapper.connection_uuid
        
        # Track current visual state to detect changes
        self._current_visual_state: Optional[EdgeVisualState] = None
        
        # Subscribe to wrapper lifecycle events
        self.wrapper.add_lifecycle_subscriber(
            self._on_wrapper_lifecycle_event
        )
        
        # Perform initial sync to UI
        self._sync_to_ui()

    def _on_wrapper_lifecycle_event(self):
        """
        Handle EdgeWrapper lifecycle events.
        
        Called by EdgeWrapper when hot reload or state changes occur.
        """
        # Process events and sync if state changed
        logging.info(
            f"UIEdge '{self.wrapper.connection_uuid}' needs update"
        )
        
        self._sync_to_ui()

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
        if not self.wrapper.is_valid:
            return EdgeVisualState(
                connection_uuid=self.wrapper.connection_uuid,
                stroke_color="#EF4444",  # Red
                stroke_width=2,
                stroke_dasharray="5,5",  # Dashed
                opacity=0.7,
                is_valid=False,
                has_warning=False
            )
        
        # State: WARNING (adapter chain changed)
        if self.wrapper.has_warning():
            return EdgeVisualState(
                connection_uuid=self.wrapper.connection_uuid,
                stroke_color="#F59E0B",  # Orange/Amber
                stroke_width=2,
                stroke_dasharray="",  # Solid
                opacity=1.0,
                is_valid=True,
                has_warning=True
            )
        
        # State: VALID (default) - use 'auto' for gradient
        return EdgeVisualState(
            connection_uuid=self.wrapper.connection_uuid,
            stroke_color="auto",  # Use gradient from pins
            stroke_width=2,
            stroke_dasharray=self.calculate_dasharray(len(self.wrapper.edge.chain_adapter_keys)),  # Solid
            opacity=1.0,
            is_valid=True,
            has_warning=False
        )

    def calculate_dasharray(self, chain_length: int) -> str:
        if chain_length == 0:
            return ""
        return "40,2" + ",2,2" * (chain_length)
    
    def _sync_to_ui(self):
        """
        Synchronize current EdgeWrapper state to Vue component.
        
        Emits SYNC_CONNECTION_ADDITION which handles both creation and updates.
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
        event = SyncConnectionAdditionEvent(
            connectionUUID=new_state.connection_uuid,
            outputNodeId=edge.output_node_id,
            outletPinId=edge.outlet_port_id,
            inputNodeId=edge.input_node_id,
            inletPinId=edge.inlet_port_id,
            isValid=new_state.is_valid,
            hasWarning=new_state.has_warning,
            strokeColor=new_state.stroke_color,
            strokeWidth=new_state.stroke_width,
            strokeDasharray=new_state.stroke_dasharray,
            opacity=new_state.opacity
        )
        
        self.sync_event_emitter(event)
        
        logging.debug(
            f"🔗 UIEdge synced: {new_state.connection_uuid} -> "
            f"color={new_state.stroke_color}, "
            f"valid={new_state.is_valid}, "
            f"warning={new_state.has_warning}"
        )


    def cleanup(self):
        """
        Clean up UIEdge resources.
        
        Similar to UINode.cleanup() pattern.
        """
        # Unsubscribe from wrapper events
        if self.wrapper:
            self.wrapper.remove_lifecycle_subscriber(
                self._on_wrapper_lifecycle_event
            )
        
        # Clear references
        self.wrapper = None
        self.sync_event_emitter = None
        self._current_visual_state = None
        
        logging.debug(f"🔗 UIEdge cleaned up: {self.ui_edge_id}")

    def is_valid(self) -> bool:
        """Check if connection is in valid state"""
        return self.wrapper.is_valid() if self.wrapper else False

    def get_connection_uuid(self) -> str:
        """Get the connection UUID"""
        return self.wrapper.connection_uuid if self.wrapper else ""
