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
from nicegui.elements.mixins.color_elements import QUASAR_COLORS, TAILWIND_COLORS
from nicegui.elements.mixins.text_element import TextElement

from haywire.core.types import DataPort, CompoundType, FlowType, LayoutDirection

from ..themes.icons import ICONS
from ..utils import generate_pin_uuid

if TYPE_CHECKING:
    from haywire.core.node.node_wrapper import NodeWrapper


class PinGlyph(TextElement):
    """A pin's Material glyph as a NATIVE ``<i>`` instead of a Quasar ``q-icon``.

    The markup is deliberately identical to what ``q-icon`` emits for a
    Material ligature — same ``<i>`` tag, same ``q-icon notranslate
    material-icons`` classes, same ligature text, same ``aria-hidden``. So
    Quasar's own ``.q-icon`` rules still supply the box (``width/height: 1em``,
    ``box-sizing: content-box``) and ``.material-icons`` still supplies the
    font. Nothing about the rendered pin changes, which matters because the
    edge layer reads ``getBoundingClientRect()`` off this element and
    ``shell.py``'s icon-dimming rules match ``.q-icon`` (guarded by
    ``:not(.connection-pin)``).

    The point is what it is NOT: a Vue component. NiceGUI renders the whole
    page as ONE component that rebuilds a VNode per element on every update,
    and a component costs roughly 3x a native tag there. Pins are the largest
    single population in a graph — one per port, 6,600 on a 300-node graph —
    so moving them off ``q-icon`` measured **723 -> 619 ms (-14%)** on a whole-page
    update. See ``.insights/project_nicegui_component_vs_native_tag.md``.

    Two things ``q-icon`` did that a native tag cannot, and are done by
    ``render_pin`` instead: ``size`` becomes an inline ``font-size``, and
    ``color`` becomes either a ``text-*`` class (Quasar/Tailwind palette name)
    or an inline ``color`` — mirroring NiceGUI's own ``TextColorElement``.
    """

    def __init__(self, icon: str) -> None:
        super().__init__(tag="i", text=icon)
        self._props["aria-hidden"] = "true"


def _pin_color_css(color: str | None) -> tuple[str, str]:
    """Split a pin colour into (extra class, inline style), as NiceGUI does.

    ``TextColorElement`` routes a palette name to a ``text-*`` class and
    anything else (the documented case — ``DataTypeIdentity.color`` is a hex
    string) to an inline ``color``. ``q-icon`` used to do this for us.
    """
    if not color:
        return "", ""
    if color in QUASAR_COLORS or color in TAILWIND_COLORS:
        return f" text-{color}", ""
    return "", f"color: {color}; "


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


def add_pin_tooltip(pin_el: ui.element, pin: DataPort, trigger_el: ui.element | None = None) -> None:
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

    ``trigger_el`` splits WHERE the tooltip lives from WHAT the user hovers to
    get it. A widget is a custom Vue component whose template has no ``<slot>``
    (``drag.vue`` has none), so a tooltip added to one is silently dropped and
    never renders — it has to be hosted on a plain parent and triggered by the
    widget.

    Trap: every crossing of a trigger costs a websocket round trip, so trigger
    areas must be SMALL and must not NEST. A trigger on a port's content column
    as well as on its pin makes the areas overlap, so one pointer movement
    fires several enters and leaves — each a round trip, each showing or
    tearing down a Quasar tooltip.

    Panning is what makes that bite: content moves under a stationary cursor,
    so a gesture generates crossings by itself, and they land in the frames the
    gesture needs. Measured at ~0.5s of freeze at the start of a pan on a
    300-node graph in Firefox (Chrome did not show it), and only with the
    cursor over a card BODY — never over the title strip, the one part of a
    card carrying no tooltip. One trigger per thing the user can point at, and
    nothing containing another. Locked down by
    ``tests/ui/skin/test_tooltip_triggers.py``.
    """
    trigger = trigger_el if trigger_el is not None else pin_el
    tooltip: ui.tooltip | None = None

    def show_tooltip() -> None:
        nonlocal tooltip
        if tooltip is None:
            # Build inside the (stable) pin element. pin_el is not torn down by
            # this handler, so its slot is safe to populate — unlike the
            # redraw-during-handler case in .insights/feedback_nicegui_async.md.
            with pin_el:
                # no-parent-event: we are the sole show/hide controller.
                # transition-duration=0: hiding a VISIBLE tooltip is the one
                # tooltip operation that can land mid-gesture, and Quasar's
                # default 300ms show/hide animation makes it an animation the
                # browser runs while the canvas is transforming underneath.
                tooltip = ui.tooltip().classes("text-xs").props("no-parent-event transition-duration=0")
                with tooltip:
                    ui.label(pin.label).classes("font-bold")
                    description = (pin.description or "").strip()
                    if description:
                        ui.label(description)
        tooltip.run_method("show")

    def hide_tooltip() -> None:
        if tooltip is not None:
            tooltip.run_method("hide")

    trigger.on("mouseenter", lambda _: show_tooltip())
    trigger.on("mouseleave", lambda _: hide_tooltip())


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

    The ``data-pin-id`` emitted below is also what makes the pin menu work:
    the canvas detects a pin structurally from it, exactly as it detects a
    node or an edge, and opens the framework's ``PinMenu``. A skin therefore
    neither opts into a pin menu nor can suppress it — that is no longer a
    host concern, and no menu attribute belongs here (ADR-0029, Routing).
    ``data-hw-menu-surface-id`` exists only for a menu the framework knows
    nothing about, and a skin adds it to its own elements, not to a pin.
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
    glyph_transform = layout.glyph_transform
    if glyph_transform:
        # Re-aim the glyph for this direction. LayoutDirection owns the mapping
        # so the transform cannot drift from the side/vector it must agree with;
        # every value is centre-origin, leaving getBoundingClientRect() — which
        # the edge layer reads — unchanged.
        #
        # Every non-L2R direction needs one, not just the vertical pair: R2L
        # moves inlets to the right edge, so an un-mirrored glyph points out of
        # the card instead of into it, and B2T reverses T2B's flow so it needs
        # the opposite quarter turn. Symmetric DATA icons hide the omission;
        # CALLBACK's directional arrows are where it shows.
        #
        # Published as a CUSTOM PROPERTY, not as `transform` directly: canvas.vue
        # scales pins on hover, on drag-anchor, and on invalid-target, each by
        # writing the whole `transform` property. A raw transform here would be
        # replaced (not composed) by any of them and the pin would snap back to
        # its unaimed orientation. Every one of those rules composes
        # `var(--hw-pin-rotate, )` in front of its scale instead.
        pin_offset += f"--hw-pin-rotate: {glyph_transform}; "
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

    # `q-icon`'s size/color props have no meaning on a native tag — see PinGlyph.
    color_class, color_style = _pin_color_css(pin.color)

    return (
        PinGlyph(icon)
        .classes(f"q-icon notranslate material-icons port connection-pin zoom-pan-lod0{color_class}")
        .style(f"font-size: {pin_size}; {color_style}{pin_offset}")
        .props(f'{common_props} data-pin-data-type="{pin_data_type}" data-pin-color="{pin.color}"')
    )


def _resolve_pin_icon(pin: DataPort) -> str | None:
    """Resolve a pin's icon for its flow type.

    Returns the icon name, or ``None`` for an unsupported flow type (signalling
    the caller to render no pin).

    A DATA pin takes the icon its type declared for that direction, and the
    ``_multi`` variant while the pin accepts several links. The fields resolve
    their own hierarchy — see ``DataTypeIdentity.__post_init__`` — so reading
    one here is enough. CONTROL and CALLBACK pins carry their icon on the port
    itself, and take ``icon_in``/``icon_out`` directly.
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
        is_compound = bool(pin.type_cls and issubclass(pin.type_cls, CompoundType))

        if pin.is_inlet():
            if pin.allow_multiple_links:
                if issubclass(stored_type, CompoundType):
                    return ci.icon_in_multi or ICONS.WEB_STORIES
                return ci.icon_in_multi or ICONS.FIBER_SMART_RECORD
            return ci.icon_in or (ICONS.VIEW_DAY if is_compound else ICONS.MY_LOCATION)

        icon = ci.icon_out_multi if pin.allow_multiple_links else ci.icon_out
        return icon or (ICONS.VIEW_DAY if is_compound else ICONS.CIRCLE)

    return None
