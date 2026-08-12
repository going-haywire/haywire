"""Framework pin-rendering helpers shared by node skins.

These were extracted from ``NodeSkin`` so any skin — including ones that do
**not** subclass ``NodeSkin`` (and therefore carry none of its layout
settings) — can render connection-compatible pins. The functions emit the
``data-*`` attributes the Vue connection layer reads; that DOM contract is the
real coupling, not any particular skin base class.

``NodeSkin`` keeps thin wrappers that call these with its settings; standalone
skins (e.g. the reroute skin) call them directly with literal geometry.
"""

from __future__ import annotations

from nicegui import ui

from haywire.core.types import DataPort, CompoundType, FlowType

from ..themes.icons import ICONS
from ..utils import generate_pin_uuid


def add_pin_tooltip(pin_el: ui.element, pin: DataPort) -> None:
    """Attach a hover tooltip showing a port's label and description.

    The description line is omitted when the port has no description.

    Lazy construction: the tooltip (a QTooltip + 1–2 labels = 3 elements) is
    built on the pin's first ``mouseenter`` rather than at render time. A large
    graph has ~one tooltip per port, all invisible until hovered — building them
    eagerly was measured at ~30% of graph-render time. Deferring to first hover
    pays that cost only for pins the user actually hovers.

    Visibility is driven explicitly by ``mouseenter`` → show / ``mouseleave`` →
    hide, and the QTooltip is given ``no-parent-event`` so Quasar does NOT also
    run its own hover show/hide. Without that, two controllers fight: the
    tooltip mounts after the current ``mouseenter`` (so Quasar misses the first
    show — the "appears on second hover" bug) and a manual ``show`` then leaves
    Quasar's hide unreconciled (so tooltips orphan on screen). Making our
    handlers the sole controller keeps the state deterministic.
    """
    tooltip: ui.tooltip | None = None

    def show_tooltip() -> None:
        nonlocal tooltip
        if tooltip is None:
            # Build inside the (stable) pin element. pin_el is not torn down by
            # this handler, so its slot is safe to populate — unlike the
            # redraw-during-handler case in .insights/feedback_nicegui_async.md.
            with pin_el:
                # no-parent-event: we are the sole show/hide controller.
                tooltip = ui.tooltip().classes("text-xs").props("no-parent-event")
                with tooltip:
                    ui.label(pin.label).classes("font-bold")
                    description = (pin.description or "").strip()
                    if description:
                        ui.label(description)
        tooltip.run_method("show")

    def hide_tooltip() -> None:
        if tooltip is not None:
            tooltip.run_method("hide")

    pin_el.on("mouseenter", lambda _: show_tooltip())
    pin_el.on("mouseleave", lambda _: hide_tooltip())


def render_pin(
    pin: DataPort,
    node_id: str,
    *,
    direction: str = "left",
    cell_style: str = "",
    pin_gutter: int,
    card_padding: int,
    pin_protrusion: int,
) -> ui.element | None:
    """Render a connection-compatible pin and return the created element.

    Emits the ``data-*`` attributes the Vue connection layer needs. Geometry is
    passed explicitly (``pin_gutter`` / ``card_padding`` / ``pin_protrusion``)
    so callers without a settings object can supply literals.

    ``cell_style`` is appended to the pin element's own style, letting the
    caller place the pin directly into a grid cell (grid-column / *-self
    centering).

    No port-context-menu attribute is attached here — that wiring
    (``data-hw-port-menu-focus-id``) is a host concern. Callers that want a
    right-click port menu add it to the returned element themselves.
    """
    pin_direction = "inlet" if pin.is_inlet() else "outlet"
    pin_uuid = generate_pin_uuid(node_id, pin.id)

    # 2D direction vector: inlets point left (-X), outlets point right (+X).
    if pin.is_inlet():
        dir_x, dir_y = "-1", "0"
    else:
        dir_x, dir_y = "1", "0"

    common_props = (
        f'id="{pin_uuid}" '
        f'data-node-id="{node_id}" '
        f'data-pin-id="{pin.id}" '
        f'data-pin-flow-type="{pin.flow_type.value}" '
        f'data-pin-dir="{pin_direction}" '
        f'data-pin-dir-x="{dir_x}" '
        f'data-pin-dir-y="{dir_y}"'
    )

    pin_size = f"{pin_gutter}px"
    # offset = card padding + half gutter (pin's natural inset) + desired protrusion
    offset_px = card_padding + pin_gutter // 2 + pin_protrusion
    pin_offset = f"position: relative; {direction}: -{offset_px}px; cursor: crosshair; {cell_style}"

    # Resolve the per-flow-type icon; everything else (classes, color,
    # data-type, props chain) is identical across all three flow types.
    icon = _resolve_pin_icon(pin)
    if icon is None:
        # Unknown / unsupported flow type — render no pin.
        return None

    # Every pin's port carries a data type; advertise it for all flow types so
    # the Vue layer's compatibility hint can match by type (CONTROL/CALLBACK
    # previously omitted it and matched only by the undefined===undefined
    # coincidence). Connection VALIDITY keys off flow-type, not this attribute.
    pin_data_type = pin.stored_type.class_identity.registry_key

    return (
        ui.icon(icon, color=pin.color, size=pin_size)
        .classes("port connection-pin zoom-pan-lod0")
        .style(pin_offset)
        .props(f'{common_props} data-pin-data-type="{pin_data_type}" data-pin-color="{pin.color}"')
    )


def _resolve_pin_icon(pin: DataPort) -> str | None:
    """Resolve a pin's icon for its flow type.

    Returns the icon name, or ``None`` for an unsupported flow type (signalling
    the caller to render no pin). Inlet/outlet and compound/multi variants pick
    different default icons; an explicit ``pin.icon_in`` / ``pin.icon_out``
    always wins.
    """
    flow = pin.flow_type
    if flow == FlowType.CONTROL:
        if pin.is_inlet():
            return pin.icon_in or ICONS.JOIN_LEFT
        return pin.icon_out or ICONS.JOIN_RIGHT

    if flow == FlowType.CALLBACK:
        if pin.is_inlet():
            return pin.icon_in or ICONS.SWIPE_LEFT_ALT
        return pin.icon_out or ICONS.SWIPE_RIGHT_ALT

    if flow == FlowType.DATA:
        stored_type = pin.stored_type
        ci = stored_type.class_identity
        if pin.is_inlet():
            if pin.allow_multiple_links:
                if issubclass(stored_type, CompoundType):
                    return ci.icon_in_multi or ICONS.WEB_STORIES
                return ci.icon_in_multi or ICONS.FIBER_SMART_RECORD
            if pin.type_cls and issubclass(pin.type_cls, CompoundType):
                return ci.icon_in or ICONS.VIEW_DAY
            return ci.icon_in or ICONS.MY_LOCATION
        if pin.type_cls and issubclass(pin.type_cls, CompoundType):
            return ci.icon_out_multi or ICONS.VIEW_DAY
        return ci.icon_out_multi or ICONS.CIRCLE

    return None
