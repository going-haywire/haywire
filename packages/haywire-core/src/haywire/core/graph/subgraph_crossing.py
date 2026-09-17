"""The vocabulary of a Subgraph boundary crossing, and the value copies across it.

A Graph-node's card and the Subgraph behind it are separate graphs, so no edge
joins them. A crossing is instead named by a **string**, and carried by the two
places a control transition travels: the ``outlet_map`` the assembler builds,
and ``ExecutionContext.control_pin``. Neither is resolved to a port — the VM
stores the inlet id without looking it up, and a worker may return any string
(``BaseNode._parse_worker_result`` only type-checks it).

Four id spaces meet here, and every conversion between them lives in this
module so the view that *builds* a crossing and the worker that *follows* one
cannot drift:

==================  =========================  =========================
name                lives on                   example
==================  =========================  =========================
boundary port id    a boundary node's port      ``exec``, ``value``
card port id        the Graph-node's pin        ``in_exec``, ``out_value``
enter crossing      G outlet / Input inlet      ``enter_in_exec``
exit crossing       Output outlet / G inlet     ``exit_exec``
==================  =========================  =========================

One token names each crossing from both ends: ``enter_in_exec`` is the virtual
outlet G leaves by *and* the virtual inlet the Subgraph Input is entered
through. That is what lets each worker decide what to do from
``control_pin`` alone.

Values cross by worker copy, not by edge: ``copy_inward`` and ``copy_outward``
write through real ports, so each write fires that port's own pipes and the
value travels the rest of the way over ordinary edges with their own adapter
chains.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..types.enums import PortType

if TYPE_CHECKING:
    from ..node.base import BaseNode

#: Prefixes namespacing a card pin by the side it mirrors. Port ids are unique
#: per node regardless of direction, and the two boundary nodes are separate
#: nodes free to use one name each — a control Subgraph has ``exec`` on both —
#: so the card cannot reuse a boundary id verbatim. Every pin is prefixed, which
#: keeps the mapping total: boundary ``x`` becomes ``in_x``, boundary ``in_x``
#: becomes ``in_in_x``, and the two never collide.
INLET_PREFIX = "in_"
OUTLET_PREFIX = "out_"

#: Prefixes naming a virtual control crossing. Distinct from the pin prefixes,
#: so a worker reading ``control_pin`` can tell which of its roles it is in.
ENTER_PREFIX = "enter_"
EXIT_PREFIX = "exit_"


# ---------------------------------------------------------------------------
# Card pins
# ---------------------------------------------------------------------------


def card_port_id(boundary_port_id: str, *, is_inlet: bool) -> str:
    """Return the Graph-node pin id mirroring a boundary port.

    Args:
        boundary_port_id: Port id on the Subgraph Input (for an inlet) or the
            Subgraph Output (for an outlet).
        is_inlet: Whether the pin being named is one of the card's inlets.
    """
    return f"{INLET_PREFIX if is_inlet else OUTLET_PREFIX}{boundary_port_id}"


def boundary_port_id(card_port_id: str) -> str | None:
    """Return the boundary port a card pin mirrors, or ``None`` if it mirrors none.

    The inverse of ``card_port_id``: exactly one prefix is stripped.
    """
    for prefix in (INLET_PREFIX, OUTLET_PREFIX):
        if card_port_id.startswith(prefix):
            return card_port_id[len(prefix) :]
    return None


def is_card_inlet_id(card_port_id: str) -> bool:
    """Return whether this card pin id names one of the card's inlets."""
    return card_port_id.startswith(INLET_PREFIX)


# ---------------------------------------------------------------------------
# Crossings
# ---------------------------------------------------------------------------


def enter_crossing_id(card_inlet_id: str) -> str:
    """Return the crossing that carries control from a card control inlet into the Subgraph.

    Args:
        card_inlet_id: One of the Graph-node's control inlets, e.g. ``in_exec``.
    """
    return f"{ENTER_PREFIX}{card_inlet_id}"


def exit_crossing_id(boundary_inlet_id: str) -> str:
    """Return the crossing that carries control from the Subgraph Output back to the card.

    Args:
        boundary_inlet_id: One of the Subgraph Output's control inlets, e.g. ``exec``.
    """
    return f"{EXIT_PREFIX}{boundary_inlet_id}"


def crossed_enter_id(crossing_id: str) -> str | None:
    """Return the card inlet an enter crossing came from, or ``None`` if not one."""
    if crossing_id.startswith(ENTER_PREFIX):
        return crossing_id[len(ENTER_PREFIX) :]
    return None


def crossed_exit_id(crossing_id: str) -> str | None:
    """Return the boundary inlet an exit crossing came from, or ``None`` if not one."""
    if crossing_id.startswith(EXIT_PREFIX):
        return crossing_id[len(EXIT_PREFIX) :]
    return None


# ---------------------------------------------------------------------------
# Value copies
# ---------------------------------------------------------------------------


def copy_inward(card: "BaseNode", subgraph_input: "BaseNode") -> None:
    """Copy the card's data inlet values onto the Subgraph Input's data outlets.

    Each write fires that outlet's pipes, so the values reach the Subgraph's own
    nodes over its real edges, with their own adapter chains. A boundary outlet
    the card has no counterpart for is skipped.

    Reads the card's inlets without resolving them: the card runs before this in
    both shapes — its entry hop in a control Subgraph, its single data run in a
    data-only one — and ``BaseNode._execute`` drains every dirty port there, so
    a lazy outer edge has already been pulled.

    Call from a worker; both nodes must be built.
    """
    for outlet in subgraph_input.get_ports(is_port_type=PortType.OUTLET, has_pin=True):
        source = card.ports.get(card_port_id(outlet.id, is_inlet=True))
        if source is not None:
            subgraph_input.out(outlet.id, source.get_value())


def copy_outward(subgraph_output: "BaseNode", card: "BaseNode") -> None:
    """Copy the Subgraph Output's data inlet values onto the card's data outlets.

    Each write fires the card outlet's pipes, so the values reach the parent
    graph over its real edges. A card outlet the Subgraph Output has no
    counterpart for is skipped.

    The Subgraph Output's own ``_execute`` has already drained its inlets, so
    they are read unresolved.
    """
    for inlet in subgraph_output.get_ports(is_port_type=PortType.INLET, has_pin=True):
        target = card.ports.get(card_port_id(inlet.id, is_inlet=False))
        if target is not None:
            # A write to a port this node does not own — the card cannot do it
            # itself, because a data-only Subgraph gives it a single run that
            # would have to precede the interior. set_value is what out() calls.
            target.set_value(inlet.get_value())
