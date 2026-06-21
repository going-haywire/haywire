from typing import TYPE_CHECKING, Any

from haywire.core.adapter.base import IAdapter
from haywire.core.edge.edge_wrapper import EdgeWrapper

if TYPE_CHECKING:
    from . import DataPort


class Pipe:
    """Single data connection from an outlet to an inlet.

    Wraps the sink port, adapter chain, lazy flag, and edge ID.
    Owns the pull operation (read outlet → transform → store in inlet).
    """

    __slots__ = ("sink", "chain", "is_lazy", "_outlet_port", "_edge_id")

    def __init__(
        self, outlet_port: "DataPort", sink: "DataPort", chain: IAdapter, is_lazy: bool, edge_id: str
    ):
        self._outlet_port = outlet_port
        self.sink = sink
        self.chain = chain
        self.is_lazy = is_lazy
        self._edge_id = edge_id

    def propagate(self):
        """Propagate outlet value through all pipe connections.

        Eager edges: pull immediately (transform + store). ``pull()`` writes the
        sink via ``set_value(edge_id=…)``, which already marks it data-dirty, so
        an explicit pre-mark would be redundant.
        Lazy edges: mark inlet dirty with pipe ref (pull deferred to execution).
        """
        if self.is_lazy:
            # Lazy: defer pull to resolve_dirty_data()
            self.sink._mark_as_data_dirty(pipe=self)
        else:
            # Eager: pull immediately; set_value() inside pull() marks the sink dirty.
            self.pull()

    def push(self, value: Any) -> None:
        """Forward an already-in-hand value through this pipe to the sink.

        Eager edges run the chain straight to the sink — no outlet re-read.
        Lazy edges defer: mark the sink dirty and let ``pull()`` read the
        outlet's stored value later. The caller must have written that value to
        the outlet first, so the deferred ``pull()`` still sees it.
        """
        if self.is_lazy:
            self.sink._mark_as_data_dirty(pipe=self)
        else:
            self._forward(value)

    def pull(self) -> None:
        """Pull the outlet's current value through the chain to the sink.

        The deferred (lazy) path: reads the outlet's stored value (always-latest
        semantics) and forwards it. ``edge_id`` signals an edge-driven update.
        """
        self._forward(self._outlet_port.get_value())

    def _forward(self, value: Any) -> None:
        """Run the adapter chain on ``value`` and store the result in the sink."""
        if value is not None:
            self.sink.set_value(self.chain.execute(value), edge_id=self._edge_id)
        else:
            self.sink.set_value(None, edge_id=self._edge_id)


class Pipes:
    """Data transport for outlet→inlet connections.

    Handles both eager (push) and lazy (pull-on-demand) propagation.
    """

    def __init__(self, outlet_port: "DataPort"):
        self._outlet_port = outlet_port
        self._pipes: dict[str, Pipe] = {}

    def add_pipe(self, edge_wrapper: EdgeWrapper):
        """Add a pipe connection"""
        assert edge_wrapper._inlet_port is not None, (
            "add_pipe requires a valid (linked) edge with inlet wired"
        )
        assert edge_wrapper.first_adapter is not None, (
            "add_pipe requires a valid edge with adapter chain built"
        )
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

    def push(self, value: Any):
        """Forward an already-in-hand value through all pipe connections."""
        for pipe in self._pipes.values():
            pipe.push(value)

    def clear(self):
        self._pipes.clear()
