
from typing import TYPE_CHECKING, Any

from haywire.core.adapter.base import IAdapter
from haywire.core.edge.edge_wrapper import EdgeWrapper

if TYPE_CHECKING:
    from .ports import DataPort

# Example showing how pipes would work with multi-value inlets
class Pipes:
    """Example pipe class for data propagation"""
    def __init__(self):
        self.sinks: dict[str, 'DataPort'] = {}
        self.chains: dict[str, IAdapter] = {}
    
    def add_pipe(self, edge_wrapper: EdgeWrapper):
        """Add a pipe connection"""
        self.sinks[edge_wrapper.connection_uuid] = edge_wrapper._inlet_port
        self.chains[edge_wrapper.connection_uuid] = edge_wrapper.first_adapter()
    
    def remove_pipe(self, edge_wrapper: EdgeWrapper):
        """Remove a pipe connection"""
        if edge_wrapper.connection_uuid in self.sinks:
            del self.sinks[edge_wrapper.connection_uuid]
            del self.chains[edge_wrapper.connection_uuid]

    def propagate(self, value: Any):
        """Propagate value through pipe using adapter chains"""
        for connection_uuid, sink in self.sinks.items():
            chain = self.chains[connection_uuid]
            converted_value = chain.execute(value)
            sink.set_value(converted_value, connection_uuid=connection_uuid)

    def clear(self):
        self.sinks.clear()
        self.chains.clear()

