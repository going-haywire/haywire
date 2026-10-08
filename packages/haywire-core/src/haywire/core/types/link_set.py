"""One end's edges of a port: the edges ending at it (incoming) or leaving it (outgoing).

Every ``DataPort`` holds two of these, ``port.incoming`` and ``port.outgoing``. An inlet
only ever fills the incoming set and an outlet the outgoing one; a swinglet may fill both.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.core.types.wire import WireRole

if TYPE_CHECKING:
    from haywire.core.edge.edge_wrapper import EdgeWrapper
    from haywire.core.types.port import DataPort


class LinkSet:
    """The edges a port holds at one end, in two tiers.

    ``linked`` holds the active edges, which build pipes. ``all`` holds every edge
    targeting this end, linked or displaced, so that one can be re-enabled when an
    active edge goes away.
    """

    __slots__ = ("_port", "is_incoming", "linked", "all")

    def __init__(self, port: DataPort, is_incoming: bool) -> None:
        self._port = port
        self.is_incoming = is_incoming
        self.linked: dict[str, EdgeWrapper] = {}
        self.all: dict[str, EdgeWrapper] = {}

    @property
    def takes_many(self) -> bool:
        """Whether this end may hold more than one linked edge at a time.

        The ceiling allows many, except where a second edge would break the mechanism:
        a ``SEQUENCE`` outgoing end (the VM keeps one transition per outlet), and an
        incoming end whose field keeps one value in total (two edges writing into it
        would race). A ``SEQUENCE`` incoming end is entered once per transition and a
        ``VISUAL`` one receives no value, so both take many. ``single_link`` narrows
        either end to one.
        """
        port = self._port
        if port.single_link:
            return False
        if not self.is_incoming:
            return not port.has_role(WireRole.SEQUENCE)
        if port.has_role(WireRole.SEQUENCE) or port.has_role(WireRole.VISUAL):
            return True
        return port._data.keeps_value_per_source()

    def add_link(self, edge_wrapper: EdgeWrapper) -> list[EdgeWrapper]:
        """Link an edge at this end, displacing the linked edges when only one is allowed.

        The edge is always tracked in ``all``. Displaced edges leave ``linked`` but stay
        in ``all``: usually one, several when ``single_link`` was set on a port that
        already held more.

        Returns:
            The displaced edges, oldest first; empty when none was replaced.
        """
        port = self._port
        displaced: list[EdgeWrapper] = []

        self.all[edge_wrapper.edge_id] = edge_wrapper

        if edge_wrapper.edge_id not in self.linked:
            if not self.takes_many:
                displaced = list(self.linked.values())
                self.linked = {edge_wrapper.edge_id: edge_wrapper}
                for old_wrapper in displaced:
                    if self.is_incoming:
                        port._data.remove_source(old_wrapper.edge_id)
                    if port.on_disconnect:
                        port._trigger_callback(port.on_disconnect, old_wrapper)
            else:
                self.linked[edge_wrapper.edge_id] = edge_wrapper

            if port.on_connect:
                port._trigger_callback(port.on_connect, edge_wrapper)

        # Dirty in any case: an existing edge may have been reconnected to a
        # different source during edge validation.
        port._mark_as_structuraly_dirty()

        return displaced

    def clear_link(self, edge_id: str) -> None:
        """Remove an edge from ``linked`` only; it stays in ``all``."""
        if edge_id in self.linked:
            port = self._port
            edge_wrapper = self.linked.pop(edge_id)
            if self.is_incoming:
                port._data.remove_source(edge_id)
                # A lazy pull still queued for this edge would deliver after it is gone.
                port._pending_lazy_pipes = {p for p in port._pending_lazy_pipes if p.edge_id != edge_id}
            port._mark_as_structuraly_dirty()

            if port.on_disconnect and edge_wrapper:
                port._trigger_callback(port.on_disconnect, edge_wrapper)

    def remove_edge(self, edge_id: str) -> None:
        """Remove an edge from both tiers."""
        if edge_id in self.linked:
            self.clear_link(edge_id)
        self.all.pop(edge_id, None)

    def is_linked_to(self, edge_id: str) -> bool:
        """Return True if the edge is in ``linked``."""
        return edge_id in self.linked

    def try_reenable(self) -> EdgeWrapper | None:
        """Return the oldest functional displaced edge to promote to linked, or ``None``.

        Only an end that takes one link and has none linked has a candidate. The caller
        calls ``link()`` on the result.
        """
        if self.takes_many:
            return None

        if self.linked:
            return None

        for edge_id, edge in self.all.items():
            if edge_id not in self.linked and edge.is_functional():
                return edge

        return None

    def valid_edges(self) -> list[EdgeWrapper]:
        """Return the linked edges that are valid."""
        return [edge for edge in self.linked.values() if edge.is_valid()]

    def detach_all(self) -> list[EdgeWrapper]:
        """Empty both tiers and return every edge that was tracked, so the caller can notify them."""
        all_edges = list(self.all.values())
        self.linked.clear()
        self.all.clear()
        return all_edges

    def adopt(self, other: LinkSet) -> None:
        """Take a copy of *other*'s edges, replacing this set's own."""
        self.linked = other.linked.copy()
        self.all = other.all.copy()
