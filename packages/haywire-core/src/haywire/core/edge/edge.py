"""
Edge data structure for Haywire graphs.

This module contains the Edge dataclass which represents a connection
between two nodes. The Edge is a pure data container - lifecycle
management is handled by EdgeWrapper.
"""

from dataclasses import dataclass, field
from typing import Any, List

from ..types import Propagation


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

    # Adapter chain metadata (for serialization/deserialization)
    chain_adapter_keys: List[str] = field(default_factory=list)
    """List of adapter registry keys in execution order."""

    propagation: Propagation | None = Propagation.EAGER
    """The mode chosen for this edge, ``None`` once fitted to a wire type that allows none.
    A locked mode overrides it; see ``EdgeWrapper.propagation``."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize edge for graph save"""
        data: dict[str, Any] = {
            "source_node_id": self.source_node_id,
            "outlet_port_id": self.outlet_port_id,
            "sink_node_id": self.sink_node_id,
            "inlet_port_id": self.inlet_port_id,
            "chain_adapter_keys": self.chain_adapter_keys,
        }
        if self.propagation is not None:
            data["propagation"] = self.propagation.value
        return data
