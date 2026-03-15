
from typing import TYPE_CHECKING

from haywire.core.adapter.base import IAdapter
from haywire.core.edge.edge_wrapper import EdgeWrapper

if TYPE_CHECKING:
    from . import DataPort


class Pipe:
    """Single data connection from an outlet to an inlet.

    Wraps the sink port, adapter chain, lazy flag, and edge ID.
    Owns the pull operation (read outlet → transform → store in inlet).
    """
    __slots__ = ('sink', 'chain', 'is_lazy', '_outlet_port', '_edge_id')

    def __init__(
        self,
        outlet_port: 'DataPort',
        sink: 'DataPort',
        chain: IAdapter,
        is_lazy: bool,
        edge_id: str
    ):
        self._outlet_port = outlet_port
        self.sink = sink
        self.chain = chain
        self.is_lazy = is_lazy
        self._edge_id = edge_id

    def propagate(self):
        """Propagate outlet value through all pipe connections.

        Eager edges: mark inlet dirty, then immediately pull (transform + store).
        Lazy edges: mark inlet dirty with pipe ref (pull deferred to execution).
        """
        if self.is_lazy:
            # Lazy: defer pull to resolve_dirty_data()
            self.sink._mark_as_data_dirty(pipe=self)
        else:
            # Eager: mark dirty + pull immediately
            self.sink._mark_as_data_dirty()
            self.pull()

    def pull(self) -> None:
        """Pull current outlet value through adapter chain to inlet.

        Reads the outlet's current value (always-latest semantics),
        transforms it, and stores it in the inlet via set_value.
        The edge_id signals edge-driven update (defers on_change).
        """
        value = self._outlet_port.get_value()
        if value is not None:
            converted_value = self.chain.execute(value)
            self.sink.set_value(
                converted_value, edge_id=self._edge_id
            )
        else:
            self.sink.set_value(
                None, edge_id=self._edge_id
            )


class Pipes:
    """Data transport for outlet→inlet connections.

    Handles both eager (push) and lazy (pull-on-demand) propagation.
    """
    def __init__(self, outlet_port: 'DataPort'):
        self._outlet_port = outlet_port
        self._pipes: dict[str, Pipe] = {}

    def add_pipe(self, edge_wrapper: EdgeWrapper):
        """Add a pipe connection"""
        uuid = edge_wrapper.edge_id
        self._pipes[uuid] = Pipe(
            outlet_port=self._outlet_port,
            sink=edge_wrapper._inlet_port,
            chain=edge_wrapper.first_adapter,
            is_lazy=edge_wrapper.is_lazy,
            edge_id=uuid,
        )

    def remove_pipe(self, edge_wrapper: EdgeWrapper):
        """Remove a pipe connection"""
        self._pipes.pop(edge_wrapper.edge_id, None)

    def propagate(self):
        """Propagate outlet value through all pipe connections."""
        for pipe in self._pipes.values():
            pipe.propagate()

    def clear(self):
        self._pipes.clear()
