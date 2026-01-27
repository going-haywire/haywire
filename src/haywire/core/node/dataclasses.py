from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class NodeErrorInfo:
    """Error information for a Haywire node operation"""
    error: str
    error_message: str
    note: list = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def add_note(self, note: str):
        """Add a note to the error info"""
        self.note.append(note)


@dataclass
class NodeBehavior:
    """Behavioral configuration of a node"""
    is_control_node: bool = False
    is_data_node: bool = True
    is_output_node: bool = False
    is_mutable: bool = False
    allows_variables: bool = False
    mute_connection: list[str] = field(default_factory=lambda: ['control_in_ID', 'control_out_ID'])

    ###################################
    # Behavioral flags for node execution.
    # These flags control how the node is treated during execution.
    ###################################

    is_loopback: bool = False
    """If True, control flow can return to this node (for loops, sequences)"""
    
    is_pure: bool = True
    """If True, node has no side effects and output depends only on inputs"""
    
    is_stateful: bool = False
    """If True, node maintains state between executions"""
    
    can_execute_async: bool = False
    """If True, node supports asynchronous execution"""
    
    # NEW: Event node flag
    is_event_node: bool = False
    """If True, this is an event node (entry point for flows)"""


@dataclass
class NodeUIConfig:
    """UI configuration and capabilities"""
    is_collapsable: bool = True
    is_condensable: bool = True
    default_color: str = '#FFFFFF'
    icon: str | None = None
    node_renderer: str | None = None
    props_renderer: str | None = None
    custom_gui: str | None = None


@dataclass
class NodeUIState:
    """Runtime UI state"""
    is_muted: bool = False
    is_collapsed: bool = False
    is_condensed: bool = False
    is_pinned: bool = False
    custom_color: str = '#000000'
    posX: float = 0
    posY: float = 0
    width: float = 100
    height: float = 100
    width_min: float = -1
    height_min: float = -1


class NodeUI:
    """
    Container for all node UI-related state and configuration.
    
    Groups UI concerns under a single namespace for cleaner API:
    - node.ui.config - Static UI configuration (set during node design)
    - node.ui.state - Runtime UI state (changes during use)
    """
    
    def __init__(self):
        self.config = NodeUIConfig()
        self.state = NodeUIState()
    
    def collapse(self) -> None:
        """Collapse the node in the editor."""
        self.state.is_collapsed = True
    
    def expand(self) -> None:
        """Expand the node in the editor."""
        self.state.is_collapsed = False
    
    def set_position(self, x: float, y: float) -> None:
        """Set node position."""
        self.state.posX = x
        self.state.posY = y
    
    def get_position(self) -> tuple[float, float]:
        """Get node position."""
        return (self.state.posX, self.state.posY)


@dataclass
class NodeUserMetadata:
    """User-defined metadata"""
    notes: list[str] = field(default_factory=list)
    custom: dict[str, Any] = field(default_factory=dict)