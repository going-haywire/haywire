"""The two boundary nodes that define a Subgraph's interface.

``SubgraphInputNode`` and ``SubgraphOutputNode`` ship carrying one port each: a
bare ``ADD`` **growing slot**. The collapse action derives the interface from the
edges that cross the selection and stamps those ports around the slot; from then
on they are the interface, and the Graph-node card mirrors their shape.

The interface is the user's, so an interface port is ``PortOrigin.RESOLVED`` and
carries a removal row, while the slot is ``DECLARED`` and permanent. Connecting
an interior port to the slot grows one more interface port — see ADR 0036.

Both are ``NodeType.BOUNDARY``, which carries neither the DATA nor the CONTROL
bit, so one pair of classes serves data and control crossings alike. That also
keeps them out of ``_execute``'s data-node shortcut, which skips a worker whose
node has no dirty port — a boundary node has nothing feeding it and must run
regardless.

They execute as ordinary nodes in the host's flow: the Subgraph Input copies the
card's inlet values onto its own outlets, and the Subgraph Output copies its
inlet values onto the card's outlets. Each write fires that port's own pipes, so
every value travels the rest of the way over real edges. Control reaches them
across virtual crossings the assembler's view supplies — see
``haywire.core.graph.subgraph_crossing``.

A boundary node carrying only its slot is legal because the nodes are
``NodeType.BOUNDARY`` — the structural validator accepts a boundary node with no
interface yet (see ``_validate_boundary_node``).

These nodes live in the framework-owned **builtin** library so headless graphs
can always load a Subgraph without importing any display-only library: they
declare their skin by registry-key *string* on their own ``props`` bag, never
importing the skin class.
"""

from __future__ import annotations

from typing import Any

from haywire.barn.builtin.types import CHOICES
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.graph.subgraph import SubgraphDefinition
from haywire.core.graph.subgraph_crossing import (
    card_port_id,
    enter_crossing_id,
    exit_crossing_id,
)
from haywire.core.node import node, BaseNode, NodeType
from haywire.core.settings.descriptor import UiState
from haywire.core.types import FlowType, PortOrigin
from haywire.core.types.enums import PortType


#: Id prefix of the growing slot. Indices are never reused: a port id is baked
#: into the id of every edge attached to it, so renumbering detaches them.
_SLOT_PREFIX = "slot_"


class _GrowsInterface(BaseNode):
    """A boundary node's growing slot, and the interface ports it grows.

    Connecting an interior port to the bare ``ADD`` slot grows an interface port
    of that port's type and puts a fresh slot below it, so the node always ends
    in one open pin. The grown port is ``PortOrigin.RESOLVED``, so the user may
    remove it; the slot is ``DECLARED`` and permanent.

    A port whose type carries ``FlowType.CONTROL`` grows a control port, which
    is what turns the Graph-node into a CONTROL node. See ADR 0036.
    """

    #: Subclass hook: the side this node's ports face.
    _SLOT_PORT_TYPE: PortType

    def _add_slot(self, index: int) -> None:
        """Add the growing slot at ``index``."""
        from haywire.barn.builtin.types import ADD

        factory = ADD.as_inlet if self._SLOT_PORT_TYPE is PortType.INLET else ADD.as_outlet
        # The rail skin falls back to the port id when a label is blank, so the
        # slot names itself for what connecting to it does.
        self.add(factory(id=f"{_SLOT_PREFIX}{index}", label="add", on_connect="hb_grow"))

    def _next_slot_index(self) -> int:
        """One past the highest slot index in use."""
        used = [
            int(port.id[len(_SLOT_PREFIX) :])
            for port in self.get_all_ports()
            if port.id.startswith(_SLOT_PREFIX)
        ]
        return max(used) + 1 if used else 0

    def hb_grow(self, port, edge_wrapper) -> None:
        """Grow an interface port of the connected port's type, and a fresh slot.

        The new port takes the connected port's label, description, widget and
        default, so an interface grown by wiring starts out documented and
        presents the affordance its counterpart does — an interior port behind
        a 0..1 slider gives the card a 0..1 slider. All of it is the user's from
        then on: an interface port is ``RESOLVED``, and the Subgraph owns its
        own interface (ADR 0036).
        """
        from haywire.barn.builtin.types import ADD

        if port.type_cls is None or not issubclass(port.type_cls, ADD):
            # Already grown. The callback fires again whenever the edge is
            # re-linked — on load, on paste, on any revalidation — which must
            # not grow a second port.
            return

        other = edge_wrapper._outlet_port if port.is_inlet() else edge_wrapper._inlet_port
        if other is None:
            return

        incoming = other.stored_type
        if incoming._is_any:
            # Both ends undecided: nothing to adopt.
            return

        # Retyped in place, keeping the slot's own id: the edge being linked is
        # already attached to it, and a port id is baked into that edge's id.
        factory = incoming.as_inlet if self._SLOT_PORT_TYPE is PortType.INLET else incoming.as_outlet
        kwargs: dict[str, Any] = {
            "id": port.id,
            "label": other.label or port.id,
            "description": other.description,
            "default": other.default,
            "origin": PortOrigin.RESOLVED,
        }
        if other.widget_key is not None:
            kwargs["widget_key"] = other.widget_key
            kwargs["widget_config"] = dict(other.widget_config)
        with self.rejig(include=[port.id]):
            self.add(factory(**kwargs))
        self._add_slot(self._next_slot_index())


@node(
    label="Subgraph Input",
    description="Defines the inlets of the Graph-node that owns this Subgraph.",
    node_type=NodeType.BOUNDARY,
    hidden=True,
    _is_subgraph_input=True,
)
class SubgraphInputNode(_GrowsInterface):
    """Carries only **outlets** — the values arriving from the parent graph.

    Named for the side it represents on the Graph-node card, not for its own
    ports: it is the card's *input* side, so inside the Subgraph it hands those
    values out. Each outlet here becomes one inlet on the Graph-node.

    Ships carrying only its growing slot. The collapse action stamps the
    interface around it, and connecting an interior inlet to the slot grows one
    more — so a Subgraph can gain an input at any time.
    """

    _SLOT_PORT_TYPE = PortType.OUTLET

    def init(self) -> None:
        # Only the growing slot. The collapse action stamps the interface around
        # it, choosing the port ids, so this node names no fixed interface id.
        self._add_slot(0)

    def worker(self, context: ExecutionContext) -> str | None:
        """Hand the card's inlet values to the Subgraph, and control with them.

        Entered through a virtual ``enter_`` crossing naming the card control
        inlet the Graph-node was entered by; leaves through this node's matching
        real control outlet, so a Subgraph with several control inlets routes
        each to its own interior chain.

        Returns the control outlet to follow, or ``None`` when the Subgraph is
        crossed by data alone and there is no control chain to continue.
        """
        # Each write fires that outlet's pipes, carrying the value inward over
        # the Subgraph's real edges.
        for source, target in self.cache.inward:
            target.set_value(source.get_value())

        return self.cache.crossings.get(context.control_pin)

    def on_assembly(self) -> tuple[bool, str | None]:
        """Pair this node's outlets with the card inlets they are copied from.

        Also resolves which control outlet each ``enter_`` crossing leads to, so
        the worker neither scans ports nor takes a crossing id apart.

        Returns:
            ``(False, reason)`` when this node sits outside a Subgraph, or in
            one that no Graph-node stands for.
        """
        definition = self.wrapper.graph if self.wrapper else None
        if not isinstance(definition, SubgraphDefinition):
            return (False, "a Subgraph Input belongs inside a Subgraph")

        card_wrapper = definition.graph_node_wrapper()
        if card_wrapper is None:
            return (False, f"no Graph-node stands for Subgraph '{definition.key}'")
        card = card_wrapper.node

        pairs = []
        crossings: dict[str, str] = {}
        for outlet in self.get_ports(is_port_type=PortType.OUTLET, has_pin=True):
            card_inlet_id = card_port_id(outlet.id, is_inlet=True)
            source = card.ports.get(card_inlet_id)
            if source is not None:
                pairs.append((source, outlet))
            if outlet.flow_type is FlowType.CONTROL:
                crossings[enter_crossing_id(card_inlet_id)] = outlet.id

        self.cache.inward = pairs
        self.cache.crossings = crossings
        return (True, None)


@node(
    label="Subgraph Output",
    description="Defines the outlets of the Graph-node that owns this Subgraph.",
    node_type=NodeType.BOUNDARY,
    hidden=True,
    _is_subgraph_output=True,
)
class SubgraphOutputNode(_GrowsInterface):
    """Carries only **inlets** — the values leaving for the parent graph.

    Named for the side it represents on the Graph-node card, not for its own
    ports: it is the card's *output* side, so inside the Subgraph it collects
    those values in. Each inlet here becomes one outlet on the Graph-node.

    Ships carrying only its growing slot. The collapse action stamps the
    interface around it, and connecting an interior outlet to the slot grows one
    more — so a Subgraph can gain an output at any time.
    """

    _SLOT_PORT_TYPE = PortType.INLET

    def init(self) -> None:
        # Only the growing slot. The collapse action stamps the interface around
        # it, choosing the port ids, so this node names no fixed interface id.
        self._add_slot(0)

    def worker(self, context: ExecutionContext) -> str | None:
        """Hand the Subgraph's results to the card, and control back out with them.

        Entered through one of this node's real control inlets; leaves through
        the matching virtual ``exit_`` crossing, which carries control to the
        Graph-node's exit hop. A Subgraph with several control inlets here — one
        per exec exit of the interior, such as a Switch's two — routes each to
        its own outlet on the card.

        Returns the crossing to follow, or ``None`` when the Subgraph is crossed
        by data alone.
        """
        # Writes ports this node does not own — the card's outlets — so each
        # write fires the card's pipes and the value leaves for the host.
        for source, target in self.cache.outward:
            target.set_value(source.get_value())

        return self.cache.crossings.get(context.control_pin)

    def on_assembly(self) -> tuple[bool, str | None]:
        """Pair this node's inlets with the card outlets they are copied onto.

        Also resolves the ``exit_`` crossing each control inlet leaves by. A
        data-only Subgraph gets no crossings, so its worker copies and stops.

        Returns:
            ``(False, reason)`` when this node sits outside a Subgraph, or in
            one that no Graph-node stands for.
        """
        definition = self.wrapper.graph if self.wrapper else None
        if not isinstance(definition, SubgraphDefinition):
            return (False, "a Subgraph Output belongs inside a Subgraph")

        card_wrapper = definition.graph_node_wrapper()
        if card_wrapper is None:
            return (False, f"no Graph-node stands for Subgraph '{definition.key}'")
        card = card_wrapper.node

        pairs = []
        crossings: dict[str, str] = {}
        for inlet in self.get_ports(is_port_type=PortType.INLET, has_pin=True):
            target = card.ports.get(card_port_id(inlet.id, is_inlet=False))
            if target is not None:
                pairs.append((inlet, target))
            if inlet.flow_type is FlowType.CONTROL:
                crossings[inlet.id] = exit_crossing_id(inlet.id)

        self.cache.outward = pairs
        self.cache.crossings = crossings
        return (True, None)
