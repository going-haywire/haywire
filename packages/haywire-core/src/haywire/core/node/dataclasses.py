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
    
    has_execute_async: bool = False
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
    node_skin: str | None = None
    props_skin: str | None = None
    custom_gui: str | None = None


@dataclass
class NodeUserMetadata:
    """User-defined metadata"""
    notes: list[str] = field(default_factory=list)
    custom: dict[str, Any] = field(default_factory=dict)