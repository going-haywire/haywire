"""Promote a node setting to a DATA port (inlet, outlet or config).

A promoted port's id is the setting's ``descriptor.storage_key``, and the port
borrows the setting's ``DataField`` cell by reference, so setting and port are
two views of one value. ``_resolve_promoted`` maps a promoted port id back to
its (bag, descriptor) pair — the single port→settings crossing. See ADR 0014
and ADR 0019.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from haywire.core.types.base import WrapperType
from haywire.core.types.enums import PortType, ShowWidgetStrategy

if TYPE_CHECKING:
    from haywire.core.node.data import NodeData
    from haywire.core.settings.descriptor import setting
    from haywire.core.settings.settings import Settings
    from haywire.core.settings.settings_node import NodeSettings

logger = logging.getLogger(__name__)


def is_field_promoted(bag: "Settings", field: str) -> bool:
    """True if ``<bag>.<field>`` is currently promoted to a port.

    False for a field that is not promoted, and for one that does not exist."""
    return bag._is_promoted(field)


def _resolve_promoted(node: "NodeData", port_id: str) -> tuple["Settings", "setting"]:
    """Resolve the (settings-bag, descriptor) pair a promoted ``port_id`` binds, by
    matching the id against each descriptor's storage_key.

    Raises ``KeyError`` if no descriptor on the node carries that key."""
    for accessor in type(node)._settings_bags:
        bag: NodeSettings = getattr(node, accessor)
        for _field, desc in type(bag)._settings_descriptors().items():
            if desc.storage_key == port_id:
                return bag, desc
    raise KeyError(port_id)


def bag_accessor(node: "NodeData", bag: "Settings") -> str | None:
    """The accessor name under which *bag* is bound on *node*, or ``None``.

    Matched by identity, so a bag of the same class on another node never
    matches.
    """
    for accessor in type(node)._settings_bags:
        if getattr(node, accessor, None) is bag:
            return accessor
    return None


def _descriptor(node: "NodeData", accessor: str, field: str) -> "setting":
    """The setting descriptor for ``<accessor>.<field>`` on *node*, including a field
    inherited from a settings-bag base class. Raises ``KeyError`` for an unknown field."""
    bag: NodeSettings = getattr(node, accessor)
    return type(bag)._settings_descriptors()[field]


def eligible_promotion_directions(descriptor: "setting") -> tuple[PortType, ...]:
    """The port directions ``descriptor`` may be promoted to.

    Read from the field's declared ``setting(promotable=...)``, default
    ``Promotable.ALL``. A ``watch()`` field seeds ``Promotable.OUTLET``, so it is
    outlet-only. See ADR 0019.
    """
    from haywire.core.settings.descriptor import Promotable

    declared = getattr(descriptor, "_promotable", Promotable.ALL)
    directions: list[PortType] = []
    if Promotable.INLET in declared:
        directions.append(PortType.INLET)
    if Promotable.OUTLET in declared:
        directions.append(PortType.OUTLET)
    if Promotable.CONFIG in declared:
        directions.append(PortType.CONFIG)
    return tuple(directions)


def _metadata_to_port_kwargs(descriptor: "setting") -> dict:
    """Build ``IType.as_inlet``/``as_outlet`` kwargs from a setting descriptor.

    Wrapper types are replaced by their element type (``OPTIONAL[INT]`` gives
    an ``INT`` port), returned under ``type_cls``. ``label`` falls back to the
    attribute name, and ``widget_key``/``widget_config`` are included only when
    set, so the port carries the setting's own widget contract.
    """
    # Wrapper settings promote as their element type (OPTIONAL[INT] -> INT pin).
    # Unset values still cross OPTIONAL -> OPTIONAL edges; see DataField.accepts_absence.
    type_cls = descriptor._type
    element = getattr(type_cls, "element_type_cls", None)
    if isinstance(type_cls, type) and issubclass(type_cls, WrapperType) and element is not None:
        type_cls = element
    kwargs: dict = {
        "label": getattr(descriptor, "_label", "") or getattr(descriptor, "_attr_name", ""),
        "description": getattr(descriptor, "_description", "") or "",
        "order": getattr(descriptor, "_order", 0),
        "type_cls": type_cls,
    }
    widget_key = getattr(descriptor, "widget_key", "")
    if widget_key:
        kwargs["widget_key"] = widget_key
    # Skip an empty widget_config; it would replace the IType's default config.
    widget_config = getattr(descriptor, "widget_config", None)
    if widget_config:
        kwargs["widget_config"] = widget_config
    return kwargs


def _bind_port(port, bag: "Settings", desc: "setting") -> None:
    """Share the setting's cell into *port*; for an inlet or config, also mark the
    field locally-set.

    An inlet's only write path is its edge and a config's is its own widget, so
    marking them makes the setting read return the shared cell instead of falling
    back through mirror resolution. An outlet is left unmarked: it is still
    written through the normal panel path, so promoting it neither freezes a
    shadow/watch field against its global nor makes an unedited field serialize
    as dirty. See ADR 0014."""
    port.bind_field(bag._cell_for(desc))
    if port.is_inlet() or port.is_config():
        bag._set_keys.add(desc.storage_key)


def regenerate_promoted_ports(node: "NodeData") -> None:
    """Regenerate every promoted port on *node* from its bags' recorded promotions.

    Call once the settings bags are restored and before edges wire, so a
    regenerated promoted inlet exists in ``node.ports`` before any edge resolves
    against it. Each port is created through ``promote_setting``, which is
    idempotent, so an already-promoted field is left alone. A recorded promotion
    matching no field — the library changed under a saved graph — is skipped with
    a logged warning.
    """
    for accessor in type(node)._settings_bags:
        bag: NodeSettings = getattr(node, accessor)
        # storage_key -> attr name, to translate the key back to promote_setting's
        # (accessor, field) arguments.
        fields = type(bag)._settings_descriptors()
        key_to_field = {desc.storage_key: name for name, desc in fields.items()}
        for storage_key, record in list(bag._promoted_keys.items()):
            field = key_to_field.get(storage_key)
            if field is None:
                logger.warning(
                    "Promoted key %r on node %r bag %r matches no field "
                    "(library changed?); skipping regeneration.",
                    storage_key,
                    node.node_id,
                    accessor,
                )
                continue
            promote_setting(node, accessor, field, record.direction, record.show_widget)


def promote_setting(
    node: "NodeData",
    accessor: str,
    field: str,
    direction: PortType = PortType.INLET,
    show_widget: "ShowWidgetStrategy | None" = None,
) -> None:
    """Promote a setting field to a DATA port in *direction*. No-op if already promoted.

    The port's id is the setting's ``storage_key``, and it borrows the setting's
    cell by reference, so setting and port are one value. An inlet or config is
    also marked locally-set; an outlet is not (see ``_bind_port``). The promotion
    is recorded on the bag, which is what serializes — the port never does.

    A promoted outlet is always ``is_linked_lazy``, since it is never driven by a
    worker ``out()`` call. A promoted config port is pinless (``flow_type=NONE``),
    so it is never linked and never lazy, and it keeps its editable row in the
    Properties panel: promoting to config adds the port's own widget wherever a
    config port renders, rather than moving the panel's.

    Args:
        direction: ``INLET``, ``OUTLET`` or ``CONFIG``. It picks the port factory
            and with it the default ``ShowWidgetStrategy`` — ``NOT_LINKED`` for
            an inlet, ``NEVER`` for an outlet, ``ALWAYS`` for a config.
        show_widget: Overrides that default for this port. ``None`` keeps the
            direction's default, which is what an interactive promotion passes;
            a value arrives from ``regenerate_promoted_ports`` restoring a choice
            made through the pin menu (see ``DataPort.set_show_widget``).

    Raises:
        ValueError: If *direction* is none of the three port types, or if
            ``eligible_promotion_directions`` does not include it.
    """
    if direction not in (PortType.INLET, PortType.OUTLET, PortType.CONFIG):
        raise ValueError(f"promote direction must be INLET, OUTLET, or CONFIG, got {direction!r}")

    desc = _descriptor(node, accessor, field)
    pid = desc.storage_key  # the setting's own key is the port id
    if pid in node.ports:
        return

    eligible = eligible_promotion_directions(desc)
    if direction not in eligible:
        raise ValueError(
            f"setting {field!r} cannot be promoted to {direction.name.lower()} "
            f"(eligible: {', '.join(d.name.lower() for d in eligible) or 'none'})"
        )

    kw = _metadata_to_port_kwargs(desc)
    type_cls = kw.pop("type_cls")
    # Forwarded only when set, so each factory's own setdefault stays the one
    # place that decides a plain promotion's widget visibility.
    if show_widget is not None:
        kw["show_widget"] = show_widget
    if direction is PortType.OUTLET:
        spec = type_cls.as_outlet(pid, promoted=True, is_linked_lazy=True, **kw)
    elif direction is PortType.CONFIG:
        spec = type_cls.as_config(pid, promoted=True, **kw)
    else:
        spec = type_cls.as_inlet(pid, promoted=True, **kw)

    bag: NodeSettings = getattr(node, accessor)
    # pid does not exist yet, so the rejig flags nothing and add() introduces the
    # port with its group/section/order bookkeeping, leaving other ports alone.
    with node.rejig(include=[pid]):
        port = node.add(spec)
    _bind_port(port, bag, desc)
    bag._set_promoted(field, direction, show_widget)


def demote_setting(node: "NodeData", port_id: str) -> None:
    """Remove the promoted port ``port_id``, release its cell binding, and clear the
    settings-side promotion record.

    No-op if the node has no such port. A port matching no setting — the library
    changed under a saved graph — is still removed."""
    if port_id not in node.ports:
        return
    try:
        bag, desc = _resolve_promoted(node, port_id)
        bag._clear_promoted(desc._attr_name)
    except KeyError:
        pass  # port matches no setting (library changed) — just remove the port
    node.ports[port_id].unbind_field()
    with node.rejig(include=[port_id]):
        pass


def remove_port(node: "NodeData", port_id: str) -> bool:
    """Remove a user-created port, releasing whatever its origin holds.

    The one verb behind the pin menu's removal row, for a port the user brought
    into being: a setting promoted to a pin, or a slot resolved from an ``ANY``
    placeholder. An author-declared port is part of what the node is and is
    refused. Any edges on the port are detached with it.

    Returns:
        ``True`` if the port was removed, ``False`` for an unknown port or one
        the user may not remove (see :meth:`DataPort.is_user_removable`).
    """
    from haywire.core.types.enums import PortOrigin

    port = node.ports.get(port_id)
    if port is None or not port.is_user_removable():
        return False

    if port.origin is PortOrigin.PROMOTED:
        demote_setting(node, port_id)
        return True

    with node.rejig(include=[port_id]):
        pass
    return True


def set_promoted_show_widget(
    node: "NodeData",
    port_id: str,
    strategy: ShowWidgetStrategy,
) -> None:
    """Set a promoted port's widget-visibility strategy, and persist the choice.

    Writes both the live port, which ``should_show_widget()`` reads at render
    time, and the bag's promotion record, which is what survives a save since a
    promoted port is regenerated rather than serialized.

    No-op for an unknown port, a port that is not promoted, or one matching no
    setting. Callers redraw; this does not.
    """
    port = node.ports.get(port_id)
    if port is None or not port.promoted:
        return
    try:
        bag, desc = _resolve_promoted(node, port_id)
    except KeyError:
        return
    port.set_show_widget(strategy)
    bag._set_promoted_show_widget(desc._attr_name, strategy)
