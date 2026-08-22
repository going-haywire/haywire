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

from typing import TYPE_CHECKING

from nicegui import ui

from haywire.core.types import DataPort, CompoundType, FlowType, LayoutDirection

from ..themes.icons import ICONS
from ..utils import generate_pin_uuid

if TYPE_CHECKING:
    from haywire.core.node.node_wrapper import NodeWrapper


def resolve_layout_direction(wrapper: "NodeWrapper") -> LayoutDirection:
    """The node's own layout direction (framework < graph < node).

    Reads ``node.props.layout_direction``, whose ``graph()`` mirror already
    resolves the chain. Anything unexpected degrades to ``LEFT_TO_RIGHT`` —
    this is on the render path, so it must never raise.
    """
    try:
        return LayoutDirection.coerce(wrapper.node.props.layout_direction)
    except Exception:
        return LayoutDirection.LEFT_TO_RIGHT


def resolve_graph_layout_direction(wrapper: "NodeWrapper") -> LayoutDirection:
    """The owning GRAPH's layout direction, ignoring any per-node override.

    For skins whose shape is dictated by the graph rather than the node — the
    reroute skin, which is a dot on a wire and must follow the wire.
    """
    try:
        return LayoutDirection.coerce(wrapper.graph.props.layout_direction)
    except Exception:
        return LayoutDirection.LEFT_TO_RIGHT


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
    layout: LayoutDirection = LayoutDirection.LEFT_TO_RIGHT,
    cell_style: str = "",
    pin_gutter: int,
    card_padding: int,
    pin_protrusion: int,
) -> ui.element | None:
    """Render a connection-compatible pin and return the created element.

    Emits the ``data-*`` attributes the Vue connection layer needs. Geometry is
    passed explicitly (``pin_gutter`` / ``card_padding`` / ``pin_protrusion``)
    so callers without a settings object can supply literals. ``card_padding``
    must be the padding on the axis this pin crosses — the caller picks it,
    because only the caller knows which padding its card actually paints.

    ``layout`` decides which card edge the pin sits on and which way its edge
    leaves: BOTH are derived from it here, and that is the point. The CSS side
    and the ``data-pin-dir-x/y`` vector must never be computed independently —
    a mismatch renders pins on the correct edge with edges curving the wrong
    way, and nothing reports it. Defaults to ``LEFT_TO_RIGHT`` so a skin that
    does not pass one keeps the historical behaviour verbatim.

    ``cell_style`` is appended to the pin element's own style, letting the
    caller place the pin directly into a grid cell (grid-column / *-self
    centering).

    No port-context-menu attribute is attached here — that wiring
    (``data-hw-port-menu-focus-id``) is a host concern. Callers that want a
    right-click port menu add it to the returned element themselves.
    """
    pin_direction = "inlet" if pin.is_inlet() else "outlet"
    pin_uuid = generate_pin_uuid(node_id, pin.id)

    # One source for both the CSS side and the direction vector.
    side = layout.side_for(pin)
    dir_x, dir_y = layout.vector_for(pin)

    common_props = (
        f'id="{pin_uuid}" '
        f'data-node-id="{node_id}" '
        f'data-pin-id="{pin.id}" '
        f'data-pin-flow-type="{pin.flow_type.value}" '
        f'data-pin-dir="{pin_direction}" '
        f'data-pin-dir-x="{dir_x}" '
        f'data-pin-dir-y="{dir_y}" '
        f'data-hw-layout="{layout.value}"'
    )

    pin_size = f"{pin_gutter}px"
    # offset = card padding + half gutter (pin's natural inset) + desired protrusion
    offset_px = card_padding + pin_gutter // 2 + pin_protrusion
    pin_offset = f"position: relative; {side}: -{offset_px}px; cursor: crosshair; "
    if layout.is_vertical:
        # The built-in CONTROL/CALLBACK glyphs (and library authors' per-type
        # icon_in/icon_out overrides) are drawn pointing left/right. Rotating
        # the element re-aims every one of them for free, including custom
        # types this module has never heard of. Rotation is about the centre,
        # so getBoundingClientRect() — which the edge layer reads — is
        # unchanged.
        #
        # Published as a CUSTOM PROPERTY, not as `transform` directly: canvas.vue
        # scales pins on hover, on drag-anchor, and on invalid-target, each by
        # writing the whole `transform` property. A raw rotation here would be
        # replaced (not composed) by any of them and the pin would snap back to
        # horizontal. Every one of those rules composes `var(--hw-pin-rotate, )`
        # in front of its scale instead.
        pin_offset += "--hw-pin-rotate: rotate(90deg); "
    pin_offset += cell_style

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
