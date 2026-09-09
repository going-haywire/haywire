"""Promote a node setting to a DATA port (inlet or outlet).

A promoted port's id IS the setting's ``descriptor.storage_key``. The port
carries only a ``promoted`` bool; it borrows the setting's DataField cell by reference
(one cell, two views). ``_resolve_promoted`` maps a promoted port id back to its
(bag, descriptor) by matching storage_key — the single port→settings crossing.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from haywire.core.types.enums import PortType, ShowWidgetStrategy

if TYPE_CHECKING:
    from haywire.core.node.data import NodeData
    from haywire.core.settings.descriptor import setting
    from haywire.core.settings.settings import Settings

logger = logging.getLogger(__name__)


def is_field_promoted(bag: "Settings", field: str) -> bool:
    """True if ``<bag>.<field>`` is currently promoted to a port.

    Consults the bag's ``_promoted_keys`` — the single source of truth.
    False for a field that is not promoted or does not exist."""
    return bag._is_promoted(field)


def _resolve_promoted(node: "NodeData", port_id: str) -> tuple["Settings", "setting"]:
    """Resolve the (bag, descriptor) a promoted ``port_id`` binds, by matching the id
    against each field's storage_key. The sole port→settings crossing."""
    for accessor in type(node)._settings_bags:
        bag = getattr(node, accessor)
        for _field, desc in type(bag)._property_settings().items():
            if desc.storage_key == port_id:
                return bag, desc
    raise KeyError(port_id)


def bag_accessor(node: "NodeData", bag: "Settings") -> str | None:
    """The accessor name under which *bag* is bound on *node*, or ``None``.

    Reverse of ``getattr(node, accessor)`` — identity comparison, so a bag of
    the same class on another node never matches. Used by the setting-row menu,
    which holds the bag object but calls ``promote_setting`` by accessor name.
    """
    for accessor in type(node)._settings_bags:
        if getattr(node, accessor, None) is bag:
            return accessor
    return None


def _descriptor(node: "NodeData", accessor: str, field: str) -> "setting":
    """The setting descriptor for ``<accessor>.<field>`` on *node*. MRO-aware
    (matches ``is_field_promoted``/``_resolve_promoted``) so a field inherited from a
    settings-bag base class resolves correctly, not just one declared directly."""
    bag = getattr(node, accessor)
    return type(bag)._property_settings()[field]


def eligible_promotion_directions(descriptor: "setting") -> tuple[PortType, ...]:
    """The single source of truth for promotion eligibility.

    Purely ``setting(promotable=...)`` (default ``ALL``). ``watch()`` seeds
    ``Promotable.OUTLET`` itself (a mirrored field has no legitimate write
    path in) — there is no separate structural override here; the declared
    flag IS the eligibility.

    Consumed by ``promote_setting`` (raises for ineligible promotions) and the
    setting-row menu (hides ineligible entries).
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
    """Project a setting descriptor's metadata into kwargs for ``IType.as_inlet``/``as_outlet``.

    The descriptor and ``DataPort`` carry the same label/description/type/order metadata
    under different attribute names (``_label`` vs ``label``); this is the single bridge
    that translates the descriptor's underscore-prefixed read side into the port-side
    kwarg names. ``type_cls`` is popped by the caller to select the IType; the rest pass
    through to the factory. Falls back to the field's attr name when no label is set.

    ``widget_key``/``widget_config`` are forwarded so a promoted port's inline
    canvas widget (ui/skin/base.py, keyed off ``port.widget_key``) carries the
    setting's own stamped contract — a CHOICES field's options, a
    numeric field's min/max, or an explicit ``widget=`` override — rather than
    silently falling back to the IType's bare identity default with an empty
    widget_config. Only forwarded when non-empty: an empty override would
    otherwise stomp ``create_port_spec``'s IType-identity default with `{}`.
    """
    kwargs: dict = {
        "label": getattr(descriptor, "_label", "") or getattr(descriptor, "_attr_name", ""),
        "description": getattr(descriptor, "_description", "") or "",
        "order": getattr(descriptor, "_order", 0),
        "type_cls": descriptor._type,
    }
    widget_key = getattr(descriptor, "widget_key", "")
    if widget_key:
        kwargs["widget_key"] = widget_key
    widget_config = getattr(descriptor, "widget_config", None)
    if widget_config:
        kwargs["widget_config"] = widget_config
    return kwargs


def _bind_port(port, bag: "Settings", desc: "setting") -> None:
    """Share the setting's cell into *port*; for an INLET or CONFIG, also mark
    the field locally-set.

    One cell, two views. INLET's only write path is the edge, and CONFIG has no
    write path but its own widget (no edge exists at all) — both are "inputs"
    (``Promotable.INPUT = INLET | CONFIG``), so marking them locally-set is what
    makes the setting's read return the shared cell's current value instead of
    falling back through the mirror-resolution chain (and what `_on_field_change`
    checks to stop re-seeding a shadow/watch field from its global once the
    field is considered promoted-and-owned). An OUTLET has no such write path of
    its own — it is still written through the normal panel/registry path,
    exactly as if it weren't promoted — so promoting it must not freeze a
    shadow/watch field against its global or make an unedited field serialize
    as dirty; only an actual local write should ever mark it. Used by
    promote_setting (interactive AND load-time regen, via
    regenerate_promoted_ports)."""
    port.bind_field(bag._cell_for(desc))
    if port.is_inlet() or port.is_config():
        bag._set_keys.add(desc.storage_key)


def regenerate_promoted_ports(node: "NodeData") -> None:
    """Regenerate every promoted port on *node* from its bag's ``_promoted_keys``
    (load-time pass).

    Settings bags are already restored (BaseNode._initialize_from_dict runs
    settings before this), so each bag's ``_promoted_keys`` holds the loaded
    promotions. This walks them and calls ``promote_setting`` — the SAME path an
    interactive promotion takes — so there is one creation path for both. The
    ``if pid in node.ports: return`` guard inside ``promote_setting`` makes this
    idempotent. Runs before edges wire (two-phase graph load), so a regenerated
    promoted inlet exists in ``node.ports`` before any edge resolves against it.
    """
    for accessor in type(node)._settings_bags:
        bag = getattr(node, accessor)
        # storage_key -> attr name, to translate the key back to promote_setting's
        # (accessor, field) arguments.
        fields = type(bag)._property_settings()
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

    Promotion = field + direction. The port borrows the setting's DataField cell
    by reference (``bind_field``) — one cell, two views. The port id IS the
    setting's ``storage_key``. An INLET or CONFIG is additionally marked
    locally-set at promote-time so the setting read returns the shared cell
    (incl. any edge-driven value for INLET) with no per-write hook — both have
    no other write path in (CONFIG has no edge at all; INLET's only write path
    IS the edge). An OUTLET is not marked locally-set — it has no write path of
    its own (still written through the normal panel/registry path), so
    promoting it must not freeze a shadow/watch field against its global or
    make an unedited field serialize as dirty (see ``_bind_port``).

    Eligibility is ``eligible_promotion_directions(desc)`` — the field's
    declared ``promotable=`` (``watch()`` seeds ``Promotable.OUTLET``; a
    ``watch()`` field is therefore never CONFIG-eligible).
    Raises for any ineligible promotion, interactive or load-time.

    A promoted outlet is always ``is_linked_lazy`` (the link-time force +
    ``on_changed → propagate``) — holds for plain, shadow, watch alike, because
    a promoted outlet is never worker-``out()``-driven. A promoted CONFIG port
    is pinless (``flow_type=NONE``) — never linked, never lazy.

    Direction selects the factory (``as_inlet``/``as_outlet``/``as_config``) and
    thus the per-direction ``ShowWidgetStrategy`` default (inlet NOT_LINKED →
    widget shows while unlinked; outlet NEVER; config ALWAYS). A promoted CONFIG
    keeps its editable widget on the Properties-panel row too (like an OUTLET,
    the setting stays the source of truth) — promoting to config ADDS the port's
    own live widget wherever a CONFIG port renders (node card / Ports Panel), it
    does not move the panel's.

    ``show_widget`` overrides that per-direction default for this port.
    ``None`` (the default) means "use the direction's" and is what an
    interactive promotion always passes; a value arrives only from
    ``regenerate_promoted_ports`` restoring a choice the user made through the
    pin menu, which is the one runtime write path (see
    ``DataPort.set_show_widget``). ADR 0003's rule that visibility is the
    *author's* decision is untouched: it governs author-declared ports, and a
    promoted port has no author behind its strategy.
    """
    if direction not in (PortType.INLET, PortType.OUTLET, PortType.CONFIG):
        raise ValueError(f"promote direction must be INLET, OUTLET, or CONFIG, got {direction!r}")

    desc = _descriptor(node, accessor, field)
    pid = desc.storage_key  # the setting's own key IS the port id
    if pid in node.ports:
        return

    # Eligibility — the single source of truth shared with the setting-row menu
    # (declared promotable= ∩ the read-only structural rule). Applies to every
    # promotion, including the load-time regen path: there are no saved graphs
    # with promoted ports yet, so there is nothing to grandfather — an ineligible
    # promotion is always a live authoring mistake and should fail loudly.
    eligible = eligible_promotion_directions(desc)
    if direction not in eligible:
        raise ValueError(
            f"setting {field!r} cannot be promoted to {direction.name.lower()} "
            f"(eligible: {', '.join(d.name.lower() for d in eligible) or 'none'})"
        )

    kw = _metadata_to_port_kwargs(desc)
    type_cls = kw.pop("type_cls")
    # Only forwarded when set: absent lets each factory's own setdefault inject
    # the per-direction default, so there is still exactly one place that
    # decides what a plain promotion looks like.
    if show_widget is not None:
        kw["show_widget"] = show_widget
    if direction is PortType.OUTLET:
        # Every promoted outlet is is_linked_lazy.
        spec = type_cls.as_outlet(pid, promoted=True, is_linked_lazy=True, **kw)
    elif direction is PortType.CONFIG:
        spec = type_cls.as_config(pid, promoted=True, **kw)
    else:
        spec = type_cls.as_inlet(pid, promoted=True, **kw)

    bag = getattr(node, accessor)
    # rejig(include=[pid]) flags only pid (which doesn't exist yet → flags nothing),
    # so add() introduces the port without disturbing the node's other ports. add()
    # keeps group/section/order/rejig bookkeeping.
    with node.rejig(include=[pid]):
        port = node.add(spec)
    # One cell, two views: share the setting's cell by reference.
    # A promoted field is locally-set for the port's lifetime: the setting
    # read returns the shared cell (incl. any edge-driven value). Bare set-membership,
    # no callback — the cell already holds the value, so promoting is value-neutral.
    _bind_port(port, bag, desc)
    # Record the promotion in the bag — the single source of truth. This is what
    # serializes (the port itself never does) and what regenerate_promoted_ports
    # reads on load. Idempotent-safe: an early return above (pid already in
    # node.ports) means we never reach here for an already-promoted field.
    bag._set_promoted(field, direction, show_widget)


def demote_setting(node: "NodeData", port_id: str) -> None:
    """Remove the promoted port ``port_id``, release its cell binding, and clear
    the settings-side promotion record.

    Mirror of ``promote_setting``: promote writes ``_promoted_keys``, demote
    clears it — the port is no longer the promotion signal, so the
    record must be maintained explicitly."""
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


def set_promoted_show_widget(
    node: "NodeData",
    port_id: str,
    strategy: ShowWidgetStrategy,
) -> None:
    """Set a promoted port's widget-visibility strategy, and persist the choice.

    Two writes, both required: the live port (what ``should_show_widget()``
    reads at render time) and the bag's promotion record (what survives a save,
    since a promoted port is regenerated rather than serialized). Writing only
    the port would work until reload and then silently revert.

    No-op for an unknown port, a port that is not promoted, or one matching no
    setting — the pin menu only offers this on a promoted pin, so those are
    defensive rather than expected.

    Callers redraw; this does not.
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
