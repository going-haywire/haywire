"""
Edge data structure for Haywire graphs.

This module contains the Edge dataclass which represents a connection
between two nodes. The Edge is a pure data container - lifecycle
management is handled by EdgeWrapper.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, List

from ..data.enums import FlowType

@dataclass
class Edge:
    """
    Data structure representing a connection between two nodes.
    
    This is a pure data container - lifecycle is managed by EdgeWrapper.
    Stores connection endpoints and adapter chain metadata for
    serialization.
    """
    
    # Connection endpoints
    output_node_id: str
    outlet_pin_id: str
    input_node_id: str
    inlet_pin_id: str
    
    # Edge classification
    edge_type: FlowType
    
    # Adapter chain metadata (for serialization/deserialization)
    adapter_registry_keys: List[str] = field(default_factory=list)
    """
    List of adapter registry keys in execution order.
    Example: ['temp_to_float', 'float_to_int']
    """
    
    # Connection ID (generated from components)
    connection_uuid: str = ""
    """UUID generated from connection components"""
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize edge for graph save"""
        return {
            'output_node_id': self.output_node_id,
            'outlet_pin_id': self.outlet_pin_id,
            'input_node_id': self.input_node_id,
            'inlet_pin_id': self.inlet_pin_id,
            'edge_type': self.edge_type.value,
            'adapter_registry_keys': self.adapter_registry_keys,
            'connection_uuid': self.connection_uuid
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Edge':
        """Deserialize edge from graph load"""
        return cls(
            output_node_id=data['output_node_id'],
            outlet_pin_id=data['outlet_pin_id'],
            input_node_id=data['input_node_id'],
            inlet_pin_id=data['inlet_pin_id'],
            edge_type=FlowType(data['edge_type']),
            adapter_registry_keys=data.get('adapter_registry_keys', []),
            connection_uuid=data.get('connection_uuid', '')
        )
