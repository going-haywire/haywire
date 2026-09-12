"""ADD port test node — grows a new pin from whatever connects to it.

Covers both forms: bare ``ADD`` slots, which adopt the connected type, and an
``ADD[TEST_STRING]`` slot, which stays TEST_STRING and lets the adapters convert.
"""

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType
from haywire.core.types import PortOrigin


@node(
    label="Add Port TestNode",
    search_tags=["testing", "add", "placeholder", "resolve", "variadic"],
    menu="testing/testbed",
    node_type=NodeType.DATA,
)
class AddPortTestNode(BaseNode):
    """Node whose ADD pins grow real ports when something connects to them.

    Starts with one undecided inlet, `add_in_0`, one undecided outlet,
    `add_out_0`, and one decided inlet, `str_in_0`, typed `ADD[TEST_STRING]`.

    Connecting to an undecided pin replaces it with a port of the connected
    type. Connecting to the decided pin replaces it with a `TEST_STRING` port,
    and anything convertible to it may connect — the value arrives converted.
    Each side appends a fresh slot below, so it always ends in one open pin.

    A resolved pin stays once its edge is gone — unplugging leaves an empty
    typed slot the user can reconnect, and removing it for good is a separate
    gesture on the pin menu. Slot indices are never reused, so the pins a saved
    graph refers to keep their ids.

    A connection between two undecided pins is ignored — neither end has a type
    to adopt — and both stay undecided.
    """

    #: Port-id prefix per side, and the label each side shows.
    _SIDES = {"in": ("add_in_", "In"), "out": ("add_out_", "Out"), "str": ("str_in_", "Str")}

    def init(self):
        from haywire.barn.builtin.types import ADD

        from haybale_testing.types.test_types import TEST_STRING

        self._add_slot("in", 0, ADD)
        self._add_slot("out", 0, ADD)
        self._add_slot("str", 0, ADD[TEST_STRING])

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def hb_resolve(self, port, edge_wrapper):
        """Retype *port* and append a new slot of the same kind."""
        from haywire.barn.builtin.types import ADD

        from haybale_testing.types.test_types import TEST_STRING

        if port.type_cls is None or not issubclass(port.type_cls, ADD):
            # Already resolved. Connecting decides a slot once, and the callback
            # fires again whenever the edge is re-linked — on load, on paste, on
            # any revalidation — which must not grow a second slot.
            return

        side = self._side_of(port.id)

        # A decided slot keeps its own type; the edge already carries the
        # conversion, so there is nothing to adopt from the other end.
        if side == "str":
            with self.rejig(include=[port.id]):
                self._add_slot(side, self._index_of(side, port.id), TEST_STRING, PortOrigin.RESOLVED)
            self._add_slot(side, self._next_index(side), ADD[TEST_STRING])
            return

        # An inlet reads the type from the outlet feeding it, and vice versa.
        other = edge_wrapper._outlet_port if port.is_inlet() else edge_wrapper._inlet_port
        if other is None:
            return

        incoming = other.stored_type
        if incoming._is_any:
            # Both ends undecided: nothing to adopt, and no new slot.
            return

        with self.rejig(include=[port.id]):
            self._add_slot(side, self._index_of(side, port.id), incoming, PortOrigin.RESOLVED)
        self._add_slot(side, self._next_index(side), ADD)

    # ------------------------------------------------------------------
    # Slot management
    # ------------------------------------------------------------------

    def _side_of(self, port_id: str) -> str:
        """The side *port_id* belongs to."""
        for side, (prefix, _) in self._SIDES.items():
            if port_id.startswith(prefix):
                return side
        raise KeyError(f"no side owns port id {port_id!r}")

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
        factory = itype.as_outlet if side == "out" else itype.as_inlet
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
