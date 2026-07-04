"""Promote a node setting to a DATA port (inlet or outlet).

A promoted port's id IS the setting's ``descriptor.storage_key`` (ADR 0015). The port
carries only a ``promoted`` bool; it borrows the setting's DataField cell by reference
(one cell, two views). ``_resolve_promoted`` maps a promoted port id back to its
(bag, descriptor) by matching storage_key — the single port→settings crossing.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from haywire.core.types.enums import PortType

if TYPE_CHECKING:
    from haywire.core.node.data import NodeData
    from haywire.core.settings.descriptor import setting
    from haywire.core.settings.settings import Settings

logger = logging.getLogger(__name__)


def is_field_promoted(bag: "Settings", field: str) -> bool:
    """True if ``<bag>.<field>`` is currently promoted to a port.

    The promoted port's id IS the setting's storage_key (ADR 0015), so a promotion is
    exactly the presence of that port on the owning node. False for a bag with no node."""
    node = bag._node
    if node is None:
        return False
    desc = type(bag)._property_settings().get(field)
    if desc is None:
        return False
    return desc.storage_key in node.ports


def _resolve_promoted(node: "NodeData", port_id: str) -> tuple["Settings", "setting"]:
    """Resolve the (bag, descriptor) a promoted ``port_id`` binds, by matching the id
    against each field's storage_key. The sole port→settings crossing (ADR 0015)."""
    for accessor in type(node)._settings_bags:
        bag = getattr(node, accessor)
        for _field, desc in type(bag)._property_settings().items():
            if desc.storage_key == port_id:
                return bag, desc
    raise KeyError(port_id)


def _descriptor(node: "NodeData", accessor: str, field: str) -> "setting":
    """The setting descriptor for ``<accessor>.<field>`` on *node*. MRO-aware
    (matches ``is_field_promoted``/``_resolve_promoted``) so a field inherited from a
    settings-bag base class resolves correctly, not just one declared directly."""
    bag = getattr(node, accessor)
    return type(bag)._property_settings()[field]


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


def _bind_port(port, bag: "Settings", desc: "setting") -> None:
    """Share the setting's cell into *port* and mark the field locally-set.

    THE bind+mark pair (ADR 0015): one cell, two views; a promoted field is
    locally-set for the port's lifetime. Used by promote_setting (interactive)
    and bind_promoted_ports (load)."""
    port.bind_field(bag._cell_for(desc))
    bag._set_keys.add(desc.storage_key)


def bind_promoted_ports(node: "NodeData") -> None:
    """Bind each promoted port on *node* to its setting's cell (load-time pass).

    Settings bags are already restored (BaseNode.from_dict runs settings before
    ports). A promoted port whose setting no longer exists degrades: stays on
    the node, promoted but unbound (see Tier-1 plan / ADR 0015 stance)."""
    for port in node.ports.values():
        if not port.promoted:
            continue
        try:
            bag, desc = _resolve_promoted(node, port.id)
        except KeyError:
            logger.warning(
                "Promoted port %r on node %r matches no setting (library changed?); leaving it unbound.",
                port.id,
                node.node_id,
            )
            continue
        _bind_port(port, bag, desc)


def promote_setting(
    node: "NodeData",
    accessor: str,
    field: str,
    direction: PortType = PortType.INLET,
) -> None:
    """Promote a setting field to a DATA port in *direction*. No-op if already promoted.

    Promotion = field + direction (P5, ADR 0014). The port borrows the setting's
    DataField cell by reference (``bind_field``) — one cell, two views. The port id
    IS the setting's ``storage_key`` (ADR 0015); the field is marked locally-set at
    promote-time so the setting read returns the shared cell (incl. any edge-driven
    value) with no per-write hook.

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

    desc = _descriptor(node, accessor, field)
    pid = desc.storage_key  # the setting's own key IS the port id (ADR 0015)
    if pid in node.ports:
        return

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

    bag = getattr(node, accessor)
    # rejig(include=[pid]) flags only pid (which doesn't exist yet → flags nothing),
    # so add() introduces the port without disturbing the node's other ports. add()
    # keeps group/section/order/rejig bookkeeping.
    with node.rejig(include=[pid]):
        port = node.add(spec)
    # One cell, two views: share the setting's cell by reference.
    # A promoted field is locally-set for the port's lifetime (ADR 0015): the setting
    # read returns the shared cell (incl. any edge-driven value). Bare set-membership,
    # no callback — the cell already holds the value, so promoting is value-neutral.
    _bind_port(port, bag, desc)


def demote_setting(node: "NodeData", port_id: str) -> None:
    """Remove the promoted port ``port_id`` and release its cell binding."""
    if port_id not in node.ports:
        return
    node.ports[port_id].unbind_field()
    with node.rejig(include=[port_id]):
        pass
