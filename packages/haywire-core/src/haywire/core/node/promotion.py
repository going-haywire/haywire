"""Promote a node setting to a DATA port (inlet or outlet).

A promoted port is an ordinary dynamic port whose id encodes the setting it binds:
``setting__<accessor>__<field>``. The id IS the binding key (no separate back-reference)
— combined with ``DataPort.promoted``, it is the whole binding signal (ADR 0014). The
port borrows the setting's DataField cell by reference (one cell, two views).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.core.types.enums import PortType

if TYPE_CHECKING:
    from haywire.core.node.data import NodeData
    from haywire.core.settings.descriptor import setting
    from haywire.core.settings.settings import Settings

_PREFIX = "setting__"
_SEP = "__"


def encode_promoted_port_id(accessor: str, field: str) -> str:
    return f"{_PREFIX}{accessor}{_SEP}{field}"


def is_promoted_port_id(port_id: str) -> bool:
    return port_id.startswith(_PREFIX) and _SEP in port_id[len(_PREFIX) :]


def decode_promoted_port_id(port_id: str) -> tuple[str, str]:
    if not is_promoted_port_id(port_id):
        raise ValueError(f"Not a promoted port id: {port_id!r}")
    body = port_id[len(_PREFIX) :]
    accessor, field = body.split(_SEP, 1)
    return accessor, field


def is_field_promoted(bag: "Settings", field: str) -> bool:
    """True if ``<bag>.<field>`` is currently promoted to a port.

    The port id is the single source of truth (ADR 0014 — ``_promoted_port_id`` is
    retired). Resolves the bag's accessor name on its owning node, then checks
    whether the encoded port id exists. Returns False if the bag has no node
    back-reference (standalone / non-node settings).
    """
    node = getattr(bag, "_node", None)
    if node is None:
        return False
    accessor = _accessor_name(node, bag)
    if accessor is None:
        return False
    return encode_promoted_port_id(accessor, field) in node.ports


def _accessor_name(node: "NodeData", bag: "Settings") -> str | None:
    """The attribute name under which *bag* is bound on *node*, or None."""
    for name in type(node)._settings_bags:
        if getattr(node, name, None) is bag:
            return name
    return None


def _descriptor(node: "NodeData", accessor: str, field: str) -> "setting":
    """The setting descriptor for ``<accessor>.<field>`` on *node*."""
    bag = getattr(node, accessor)
    return type(bag).__dict__[field]


def _metadata_to_port_kwargs(descriptor: "setting") -> dict:
    """Project a setting descriptor's metadata into kwargs for ``IType.as_inlet``/``as_outlet``.

    The descriptor and ``DataPort`` carry the same label/description/type/order metadata
    under different attribute names (``_label`` vs ``label``); this is the single bridge
    that translates the descriptor's underscore-prefixed read side into the port-side
    kwarg names. ``type_cls`` is popped by the caller to select the IType; the rest pass
    through to the factory. Falls back to the field's attr name when no label is set.
    """
    return {
        "label": getattr(descriptor, "_label", "") or getattr(descriptor, "_attr_name", ""),
        "description": getattr(descriptor, "_description", "") or "",
        "order": getattr(descriptor, "_order", 0),
        "type_cls": getattr(descriptor, "_type"),
    }


def promote_setting(
    node: "NodeData",
    accessor: str,
    field: str,
    direction: PortType = PortType.INLET,
) -> None:
    """Promote a setting field to a DATA port in *direction*. No-op if already promoted.

    Promotion = field + direction (P5, ADR 0014). The port borrows the setting's
    DataField cell by reference (``bind_field``) — one cell, two views. The port id
    encodes the binding (``setting__<accessor>__<field>``); the value round-trips
    through the settings block only, so the port itself is value-less.

    Eligibility is TWO orthogonal flag checks — not a per-kind matrix:

    1. ``descriptor._read_only`` (a ``watch()`` field) ⇒ **outlet only**. A
       read-only field has no write path in, so it can only be a read path out.
    2. ``direction == OUTLET`` ⇒ the port is ``is_linked_lazy`` (Task 5 wires the
       link-time force + ``on_changed → propagate``). Holds for EVERY promoted
       outlet — plain, shadow, watch alike — because a promoted outlet is never
       worker-``out()``-driven.

    Direction selects the factory (``as_inlet``/``as_outlet``) and thus the
    per-direction ``ShowWidgetStrategy`` default (inlet NOT_LINKED → widget shows
    while unlinked; outlet NEVER). Do NOT pass ``show_widget`` explicitly.
    """
    if direction not in (PortType.INLET, PortType.OUTLET):
        raise ValueError(f"promote direction must be INLET or OUTLET, got {direction!r}")

    pid = encode_promoted_port_id(accessor, field)
    if pid in node.ports:
        return

    desc = _descriptor(node, accessor, field)
    # Flag check 1: a read-only (watch) field can only be an outlet.
    if getattr(desc, "_read_only", False) and direction is not PortType.OUTLET:
        raise ValueError("a read-only (watch) setting can only be promoted to an outlet")

    kw = _metadata_to_port_kwargs(desc)
    type_cls = kw.pop("type_cls")
    if direction is PortType.OUTLET:
        # Flag check 2: every promoted outlet is is_linked_lazy (Task 5 acts on it).
        spec = type_cls.as_outlet(pid, promoted=True, is_linked_lazy=True, **kw)
    else:
        spec = type_cls.as_inlet(pid, promoted=True, **kw)
    # rejig(include=[pid]) flags only pid (which doesn't exist yet → flags nothing),
    # so add() introduces the port without disturbing the node's other ports. add()
    # routes through DataPort.from_spec, whose promoted branch binds the port to
    # the setting's P4 cell by reference (one cell, two views — no second value).
    with node.rejig(include=[pid]):
        node.add(spec)
    # The port id + DataPort.promoted are the whole binding signal (ADR 0014).
    # No descriptor flag: the setting stays oblivious to ports, and the port
    # shares the setting's cell so reads agree.


def demote_setting(node: "NodeData", port_id: str) -> None:
    """Remove the promoted port ``port_id`` and release its cell binding."""
    if port_id not in node.ports:
        return
    node.ports[port_id].unbind_field()
    with node.rejig(include=[port_id]):
        pass
