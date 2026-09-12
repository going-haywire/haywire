"""ANY port test node — resolves a placeholder pin from the connected type.

Grows a fresh ANY slot each time the trailing one is filled, on both the inlet
and outlet side. A resolved slot is marked ``PortOrigin.RESOLVED`` and stays
until the user removes it, which is the variadic-port pattern ANY exists for.
"""

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType
from haywire.core.types import PortOrigin


@node(
    label="Any Port TestNode",
    search_tags=["testing", "any", "placeholder", "resolve", "variadic"],
    menu="testing/testbed",
    node_type=NodeType.DATA,
)
class AnyPortTestNode(BaseNode):
    """Node whose ANY pins adopt the type of whatever is connected to them.

    Starts with one undecided inlet, `any_in_0`, and one undecided outlet,
    `any_out_0`. Connecting to either replaces it with a port of the connected
    type and appends a fresh ANY slot below, so each side always ends in
    exactly one undecided pin.

    A resolved pin stays once its edge is gone — unplugging leaves an empty
    typed slot the user can reconnect, and removing it for good is a separate
    gesture on the pin menu. Slot indices are never reused, so the pins a saved
    graph refers to keep their ids.

    A connection between two ANY pins is ignored — neither end has a type to
    adopt — and both stay undecided.
    """

    #: Port-id prefix per side, and the label each side shows.
    _SIDES = {"in": ("any_in_", "In"), "out": ("any_out_", "Out")}

    def init(self):
        from haywire.barn.builtin.types import ANY

        self.add(
            ANY.as_inlet(
                id="any_in_0",
                label="In 0",
                on_connect="hb_resolve",
                on_disconnect="hb_release",
            )
        )
        self.add(
            ANY.as_outlet(
                id="any_out_0",
                label="Out 0",
                on_connect="hb_resolve",
                on_disconnect="hb_release",
            )
        )

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def hb_resolve(self, port, edge_wrapper):
        """Retype *port* to the type at the other end and append a new ANY slot."""
        from haywire.barn.builtin.types import ANY

        # An inlet reads the type from the outlet feeding it, and vice versa.
        other = edge_wrapper._outlet_port if port.is_inlet() else edge_wrapper._inlet_port
        if other is None:
            return

        incoming = other.stored_type
        if incoming._is_any:
            # Both ends undecided: nothing to adopt, and no new slot.
            return

        side = "in" if port.is_inlet() else "out"
        with self.rejig(include=[port.id]):
            self._add_slot(side, self._index_of(side, port.id), incoming, PortOrigin.RESOLVED)
        self._add_slot(side, self._next_index(side), ANY)

    # ------------------------------------------------------------------
    # Slot management
    # ------------------------------------------------------------------

    def _index_of(self, side: str, port_id: str) -> int:
        """The numeric suffix of *port_id* on *side*."""
        prefix, _ = self._SIDES[side]
        return int(port_id[len(prefix) :])

    def _next_index(self, side: str) -> int:
        """One past the highest index in use on *side*.

        Indices are never reused: a port id is baked into the id of every edge
        attached to it (see ``generate_edge_uuid``), so renumbering a slot
        silently detaches its edges. Gaps left by a removed slot stay.
        """
        prefix, _ = self._SIDES[side]
        used = [self._index_of(side, p.id) for p in self.get_all_ports() if p.id.startswith(prefix)]
        return max(used) + 1 if used else 0

    def _add_slot(self, side: str, index: int, itype, origin=None) -> None:
        """Add one slot of *itype* at *index* on *side*."""
        prefix, label = self._SIDES[side]
        factory = itype.as_inlet if side == "in" else itype.as_outlet
        kwargs = {} if origin is None else {"origin": origin}
        self.add(
            factory(
                id=f"{prefix}{index}",
                label=f"{label} {index}",
                on_connect="hb_resolve",
                **kwargs,
            )
        )

    def worker(self, context: ExecutionContext) -> str | None:
        return None
