
from typing import TYPE_CHECKING, Any

from haywire.core.adapter.base import IAdapter
from haywire.core.edge.edge_wrapper import EdgeWrapper

if TYPE_CHECKING:
    from . import DataPort

class Pipes:
    """Data transport for outlet→inlet connections.

    Handles both eager (push) and lazy (pull-on-demand) propagation.
    """
    def __init__(self, outlet_port: 'DataPort'):
        self._outlet_port = outlet_port
        self.sinks: dict[str, 'DataPort'] = {}
        self.chains: dict[str, IAdapter] = {}
        self.lazy_flags: dict[str, bool] = {}

    def add_pipe(self, edge_wrapper: EdgeWrapper):
        """Add a pipe connection"""
        uuid = edge_wrapper.connection_uuid
        self.sinks[uuid] = edge_wrapper._inlet_port
        self.chains[uuid] = edge_wrapper.first_adapter
        self.lazy_flags[uuid] = edge_wrapper.is_lazy

    def remove_pipe(self, edge_wrapper: EdgeWrapper):
        """Remove a pipe connection"""
        uuid = edge_wrapper.connection_uuid
        if uuid in self.sinks:
            del self.sinks[uuid]
            del self.chains[uuid]
            del self.lazy_flags[uuid]

    def propagate(self, value: Any):
        """Propagate value through pipe using adapter chains.

        Eager edges: transform value and push to inlet immediately.
        Lazy edges: skip transform, mark inlet dirty for later pull.
        """
        for connection_uuid, sink in self.sinks.items():
            if self.lazy_flags.get(connection_uuid, False):
                # Lazy: don't transform, just mark inlet dirty with pipe ref
                sink._mark_as_data_dirty(pipe=self, connection_uuid=connection_uuid)
            else:
                # Eager: transform and push
                if value is not None:
                    chain = self.chains[connection_uuid]
                    converted_value = chain.execute(value)
                    sink.set_value(converted_value, connection_uuid=connection_uuid)
                else:
                    sink.set_value(None, connection_uuid=connection_uuid)

    def pull_lazy(self, connection_uuid: str) -> None:
        """Pull current outlet value through adapter chain to inlet.

        Called during resolve_dirty_data() at execution time.
        Reads the outlet's current value (always-latest semantics).
        """
        value = self._outlet_port.get_value()
        sink = self.sinks[connection_uuid]
        if value is not None:
            chain = self.chains[connection_uuid]
            converted_value = chain.execute(value)
            sink.set_value_by_lazy_link(converted_value, connection_uuid=connection_uuid)
        else:
            sink.set_value_by_lazy_link(None, connection_uuid=connection_uuid)

    def clear(self):
        self.sinks.clear()
        self.chains.clear()
        self.lazy_flags.clear()
