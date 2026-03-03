"""
Edge data structure for Haywire graphs.

This module contains the Edge dataclass which represents a connection
between two nodes. The Edge is a pure data container - lifecycle
management is handled by EdgeWrapper.
"""

from dataclasses import dataclass, field
from typing import Any, List

from ..types import FlowType

@dataclass
class Edge:
    """
    Data structure representing a connection between two nodes.
    
    This is a pure data container - lifecycle is managed by EdgeWrapper.
    Stores connection endpoints and adapter chain metadata for
    serialization.
    """
    
    # Edge endpoints
    source_node_id: str
    outlet_port_id: str
    sink_node_id: str
    inlet_port_id: str
    
    # Edge classification
    edge_type: FlowType
    
    # Adapter chain metadata (for serialization/deserialization)
    chain_adapter_keys: List[str] = field(default_factory=list)
    """List of adapter registry keys in execution order."""

    # Lazy propagation
    is_lazy: bool = False
    """If True, data is pulled on-demand instead of pushed eagerly."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize edge for graph save"""
        return {
            'source_node_id': self.source_node_id,
            'outlet_port_id': self.outlet_port_id,
            'sink_node_id': self.sink_node_id,
            'inlet_port_id': self.inlet_port_id,
            'edge_type': self.edge_type.value,
            'chain_adapter_keys': self.chain_adapter_keys,
            'is_lazy': self.is_lazy
        }
    
