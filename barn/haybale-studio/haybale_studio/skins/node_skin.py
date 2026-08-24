from abc import ABC
from typing import TYPE_CHECKING, List
from nicegui import ui

from haywire.core.errors import HaywireException
from haywire.core.types import DataPort, LayoutDirection, PortType
from haywire.core.node.node_wrapper import NodeWrapper

from haywire.ui.skin.base import BaseSkin
from haywire.ui.skin.pin_render import render_pin, add_pin_tooltip, resolve_layout_direction
from haywire.ui import elements as hui
from haywire.ui.utils import generate_pin_uuid

from ..settings.node_skin_settings import NodeSkinSettings

if TYPE_CHECKING:
    from haywire.ui.widget.factory_interface import IWidgetFactory
    from haywire.core.node.node_warning import NodeWarning


class NodeSkin(BaseSkin, ABC):
    """
    Base class for all NiceGui NodeSkin classes.

    NodeSkin instances are cached and reused by the SkinFactory. They hold a
    NodeUISettings instance for live access to layout and visibility settings,
    but carry no per-node render state.

    Layout values are driven by NodeUISettings and read on every render call:
        card_padding    — horizontal padding applied to the card (px).
        pin_gutter      — width of the pin column (px). Also sets the icon size.
        pin_protrusion  — how far the pin center sits outside the card's visible edge (px).
                          0 = flush with card border; positive = further out;
                          negative = pin pulled inward.
        content_gap     — offset between the gutter column edge and the label/widget (px).
        pin_row_height  — height of the pin cell, sets vertical centering target (px)
    """

    def __init__(self, widget_factory: "IWidgetFactory"):
        super().__init__(widget_factory)
        self._ui_settings = NodeSkinSettings()

    @property
    def CARD_H_PADDING(self) -> int:  # noqa: N802
        return self._ui_settings.card_padding

    @property
    def PIN_GUTTER(self) -> int:  # noqa: N802
        return self._ui_settings.pin_gutter

    @property
    def PIN_PROTRUSION(self) -> int:  # noqa: N802
        return self._ui_settings.pin_protrusion

    @property
    def CONTENT_GAP(self) -> int:  # noqa: N802
        return self._ui_settings.content_gap

    @property
    def PIN_ROW_HEIGHT(self) -> int:  # noqa: N802
        return self._ui_settings.pin_row_height

    @property
    def PIN_COLUMN_WIDTH(self) -> int:  # noqa: N802
        return self._ui_settings.pin_column_width

    @property
    def CARD_V_PADDING(self) -> int:  # noqa: N802
        return self._ui_settings.card_padding_block

    def vertical_card_style(self) -> str:
        """Extra card CSS a vertical layout needs, for skins to append.

        Two things, both load-bearing:

        - the block padding is PAINTED, not merely read. ``render_pin`` offsets
          every pin against ``CARD_V_PADDING``; if the card actually paints
          something else, all pins seat off their edge identically — which
          reads as a design choice rather than a bug.
        - ``position: relative`` makes the card the containing block for the
          absolutely-positioned pin strips (see :meth:`render_pin_strip`).
        """
        v = self.CARD_V_PADDING
        return f"position: relative; padding-top: {v}px; padding-bottom: {v}px;"

    def layout_of(self, wrapper: NodeWrapper) -> LayoutDirection:
        """Resolve this node's layout direction.

        A pure function of the wrapper on purpose: SkinFactory caches ONE skin
        instance per registry key across every node in every open graph, so
        direction must never be stored on ``self``.
        """
        return resolve_layout_direction(wrapper)

    def render_port(
        self,
        port: DataPort,
        wrapper: NodeWrapper,
        widget_classes: str = "",
        layout: LayoutDirection | None = None,
    ):
        """Render a port according to its port type.

        In a vertical layout inlets and outlets belong in a pin strip on the
        card edge (see :meth:`render_pin_strip`), not here — a bare pin has no
        room for the label/widget column this builds. Config ports are pinless
        and render identically in every direction.
        """
        layout = self.layout_of(wrapper) if layout is None else layout
        if port.is_config():
            self._render_config(port, wrapper, widget_classes="widget-container zoom-pan-lod2")
        elif port.is_inlet() or port.is_outlet():
            self._render_port_horizontal(
                port,
                wrapper,
                side=layout.side_for(port),
                layout=layout,
                widget_classes="widget-container zoom-pan-lod2",
            )

    def _render_port_horizontal(
        self,
        port: DataPort,
        wrapper: NodeWrapper,
        *,
        side: str,
        layout: LayoutDirection,
        widget_classes: str = "",
    ):
        """Render a port as `pin column | content` (or the mirror of it).

        ``side`` is ``"left"`` or ``"right"`` and decides the grid column order
        and which margin gets the tight ``CONTENT_GAP``: the content inset
        matches regardless of which side the pin is on. The pin is centered in
        its ``PIN_GUTTER``-wide cell and ``overflow: visible`` lets it straddle
        the card edge. ``align-self: center`` on the content matches the pin, so
        label and widget share the pin's vertical center.
        """
        g, gap, h = self.PIN_GUTTER, self.CONTENT_GAP, self.PIN_ROW_HEIGHT
        pin_first = side == "left"
        columns = f"{g}px 1fr" if pin_first else f"1fr {g}px"
        pin_column, content_column = (1, 2) if pin_first else (2, 1)
        content_margins = (
            f"margin-left: {gap}px; margin-right: {g}px;"
            if pin_first
            else f"margin-left: {g}px; margin-right: {gap}px;"
        )
        content_align = "" if pin_first else "align-items: flex-end;"

        with ui.element("div").style(
            f"display: grid; grid-template-columns: {columns}; width: 100%; align-items: start; "
            "overflow: visible;"
        ):
            if pin_first:
                self._render_pin(
                    port,
                    wrapper,
                    layout=layout,
                    cell_style=(
                        f"grid-column: {pin_column}; justify-self: center; "
                        f"align-self: center; min-height: {h}px;"
                    ),
                )

            with (
                ui.element("div")
                .classes("compact-fields")
                .style(
                    f"grid-column: {content_column}; align-self: center; display: flex; "
                    f"flex-direction: column; {content_align} {content_margins} min-width: 0;"
                )
            ):
                if self._ui_settings.show_labels:
                    ui.label(port.label).classes("text-xs zoom-pan-lod2")
                if port.widget_key is not None and port.should_show_widget():
                    self.render_widget(port, wrapper.node_id, classes=widget_classes)

            if not pin_first:
                self._render_pin(
                    port,
                    wrapper,
                    layout=layout,
                    cell_style=(
                        f"grid-column: {pin_column}; justify-self: center; "
                        f"align-self: center; min-height: {h}px;"
                    ),
                )

    def render_pin_strip(
        self,
        ports: List[DataPort],
        wrapper: NodeWrapper,
        layout: LayoutDirection,
        ghost_for: "PortType | None" = None,
    ):
        """Render bare pins in a row along one card edge, for vertical layouts.

        No labels and no widgets: a pin strip has no room for them, and the
        properties editor already exposes every inlet/outlet value. Tooltips
        therefore carry the whole identification burden here — they stay wired
        even though `_render_pin` makes them conditional on the setting.

        ``ghost_for`` adds this direction's root ghost pin to the strip. The
        strip IS the card edge, which is the only place a ghost's outward offset
        resolves correctly — inline in a mid-card header row it would just shift
        16px inward.

        The strip takes NO part in the card's layout. Its pins are pushed out
        past the border by ``position: relative``, which leaves them in flow, so
        an in-flow strip reserves a full pin-row of empty space inside the card
        — the gap between the border and the node title. Collapsing that with a
        negative margin is not enough: the strip stays a flex item of the card,
        so the card's ``row-gap`` still allocates a gap slot beside it. Only
        ``position: absolute`` takes it out of flex layout altogether.

        Positioned against the card's PADDING box (``top``/``bottom`` =
        ``CARD_V_PADDING``), so each pin's static position is exactly where it
        sat in flow and ``render_pin``'s ``card_padding + gutter//2 +
        protrusion`` offset lands it on the border unchanged. The explicit
        ``height`` keeps that true when the strip holds only the smaller ghost
        pin.

        Requires the card to be a containing block; skins get that by styling
        their card through :meth:`vertical_card_style`, which sets
        ``position: relative`` explicitly rather than relying on Quasar's
        ``.q-card`` default.
        """
        if not ports and ghost_for is None:
            return
        w = self.PIN_COLUMN_WIDTH
        h = self.PIN_GUTTER
        v = self.CARD_V_PADDING
        # Which card edge this strip sits on.
        if ports:
            edge = layout.side_for(ports[0])
        else:
            edge = layout.inlet_side if ghost_for == PortType.INLET else layout.outlet_side
        with ui.element("div").style(
            "display: flex; flex-direction: row; justify-content: flex-start; "
            "align-items: center; overflow: visible; flex-wrap: nowrap; "
            f"position: absolute; left: 0; right: 0; {edge}: {v}px; height: {h}px;"
        ):
            if ghost_for is not None:
                self._render_root_ghost_pins(wrapper, layout, only=ghost_for)
            for port in sorted(ports, key=lambda p: p.order):
                self._render_pin(
                    port,
                    wrapper,
                    layout=layout,
                    cell_style=f"flex: 0 0 auto; min-width: {w}px; text-align: center;",
                )

    def _render_config(self, port, wrapper: NodeWrapper, widget_classes: str = ""):
        """Render a config port — no pin, indented symmetrically to align with inlet/outlet labels."""
        indent = max(0, self.PIN_GUTTER + self.CONTENT_GAP)
        with (
            ui.element("div")
            .classes("compact-fields")
            .style(
                f"display: flex; flex-direction: column; width: 100%; "
                f"padding-left: {indent}px; padding-right: {indent}px;"
            )
        ) as config_row:
            if self._ui_settings.show_labels:
                ui.label(port.label).classes("text-xs zoom-pan-lod2")
            if port.widget_key is not None and port.should_show_widget():
                self.render_widget(port, wrapper.node_id, classes=widget_classes)

        # Config ports render no pin, so they cannot carry a pin tooltip.
        # Attach the same label/description tooltip to the whole config row.
        if self._ui_settings.show_tooltips:
            add_pin_tooltip(config_row, port)

    def _render_pin(
        self,
        pin: DataPort,
        wrapper: NodeWrapper,
        layout: LayoutDirection | None = None,
        cell_style: str = "",
    ):
        """Render a pin with connection system compatibility.

        Thin wrapper over the framework ``render_pin`` helper, supplying this
        skin's geometry settings. ``cell_style`` is forwarded to place the pin
        into a grid cell. Wires the right-click port menu and attaches a hover
        tooltip when enabled in settings.

        The padding handed to ``render_pin`` must be the one on the axis this
        pin crosses — horizontal pins clear the card's left/right padding,
        vertical pins its top/bottom padding. Passing the wrong one seats every
        pin slightly off its edge, identically on every node, which reads as a
        design choice rather than a bug.
        """
        layout = self.layout_of(wrapper) if layout is None else layout
        pin_el = render_pin(
            pin,
            wrapper.node_id,
            layout=layout,
            cell_style=cell_style,
            pin_gutter=self.PIN_GUTTER,
            card_padding=self.CARD_V_PADDING if layout.is_vertical else self.CARD_H_PADDING,
            pin_protrusion=self.PIN_PROTRUSION,
        )
        if pin_el is not None:
            # No menu attribute: the pin menu is structural now. The canvas
            # detects a pin from the `data-pin-id` render_pin already emits,
            # and which surface it opens is the framework's decision — a skin
            # neither opts in nor can suppress it (ADR-0029, Routing).
            if self._ui_settings.show_tooltips:
                add_pin_tooltip(pin_el, pin)

    def _render_root_ghost_pins(
        self,
        wrapper: NodeWrapper,
        layout: LayoutDirection | None = None,
        only: "PortType | None" = None,
    ):
        """
        Render inline ghost pins into the current flex context.

        Both are regular flex items — no absolute positioning. Using inline flex
        items means getBoundingClientRect() always returns correct screen
        coordinates for the JavaScript edge-drawing code, regardless of which
        element acts as the CSS positioning context.

        Horizontally both go in the header row: the inlet takes natural order
        (left end) and the outlet uses `order: 999` so flexbox places it last
        (right end), after the node title and any hidden-port pins.

        Vertically the caller renders them one at a time into the matching edge
        strip (``only=``), because the strip IS the card edge. A ghost left in
        the header row would offset against a mid-card row — `top: -16px` there
        moves it 16px further INTO the card, not out to the edge.

        Sides and vectors both come from LayoutDirection so they cannot drift
        apart — the ghost pins used to carry a third hardcoded copy of them.
        """
        layout = self.layout_of(wrapper) if layout is None else layout
        node_id = wrapper.node_id
        vertical = layout.is_vertical

        for pin_id, side, (dir_x, dir_y), is_inlet in (
            ("root_in", layout.inlet_side, layout.inlet_vector, True),
            ("root_out", layout.outlet_side, layout.outlet_vector, False),
        ):
            if only is not None and (only == PortType.INLET) != is_inlet:
                continue
            # Horizontal outlets are pushed to the far end of the flex row;
            # vertically each ghost is alone in its own strip.
            order = "order: 999; " if (not vertical and not is_inlet) else ""
            # Vertically the ghost shares a strip with the real pins, so it
            # takes render_pin's offset verbatim — same padding, same gutter
            # half (the strip's height comes from the 20px pins, not from the
            # ghost's own 12px box), same protrusion. That lands every pin on
            # the strip on one edge line. The historical -16px literal happens
            # to match the default horizontal padding and says nothing about
            # the block axis, which is why it left the ghost inside the card.
            offset = self.CARD_V_PADDING + self.PIN_GUTTER // 2 + self.PIN_PROTRUSION if vertical else 16
            (
                ui.element("div")
                .classes("connection-pin zoom-pan-lod0")
                .style(
                    f"{order}width: 12px; height: 12px; border-radius: 50%; flex-shrink: 0; "
                    "background: var(--hw-ghost-pin); border: 1px dashed var(--hw-ghost-pin); "
                    f"cursor: default; {side}: -{offset}px;"
                )
                .props(
                    f'id="{generate_pin_uuid(node_id, pin_id)}" data-node-id="{node_id}" '
                    f'data-pin-id="{pin_id}" '
                    f'data-pin-flow-type="ghost" data-pin-dir="{"inlet" if is_inlet else "outlet"}" '
                    f'data-pin-dir-x="{dir_x}" data-pin-dir-y="{dir_y}" '
                    f'data-hw-layout="{layout.value}" data-pin-color="#888888"'
                )
            )

    def _render_diagnostics_button(
        self,
        errors: List["HaywireException"],
        warnings: List["NodeWarning"],
        node_id: str,
        deprecation_str: str = "",
    ) -> None:
        """Render a single badge unifying errors and advisory warnings.

        One icon, one floating count (errors + warnings + deprecation), colored
        by the highest severity present: red when the node has any runtime error,
        otherwise amber for advisory-only notices.

        Left-click opens one popup listing errors first (fatal), then advisory
        warnings and any deprecation notice. Right-click still falls through to
        the selection context menu (via `data-node-id`), which carries the Node
        Errors panel on ``SelectionMenu``.

        Args:
            errors: Runtime errors (fatal — make the node invalid).
            warnings: Advisory NodeWarning records (non-fatal).
            node_id: Node ID used by canvas.vue to resolve the active node.
            deprecation_str: Optional deprecation notice from node identity.
        """
        has_errors = bool(errors)
        # One count covering every diagnostic surfaced in the popup.
        total = len(errors) + len(warnings) + (1 if deprecation_str else 0)

        # Highest severity drives the color: red if any fatal error, else amber.
        color = "red" if has_errors else "amber"

        btn = ui.button(icon=hui.icon.warning, color=color).props("flat dense round")
        btn.classes("text-xl px-2 py-1")
        btn.style("position: absolute; top: -25px;")
        btn.props(f'data-node-id="{node_id}"')
        with btn:
            ui.badge(str(total), color=color).props("floating")

            # ui.menu renders on Layer 2 (--hw-bg-elevated) per the design system.
            # Body copy stays quiet (body/dim tokens) — severity lives on the badge
            # icon, not the prose. Messages wrap, so override `truncate`.
            with ui.menu(), ui.column().classes("p-2 gap-1").style("max-width: 22rem"):
                if errors:
                    hui.section_label("Errors")
                    for e in errors:
                        ui.label(e.message).classes("text-sm hw-text-body whitespace-normal")
                if deprecation_str:
                    hui.section_label("Deprecated")
                    ui.label(deprecation_str).classes("text-sm hw-text-body whitespace-normal")
                if warnings:
                    hui.section_label("Compatibility warnings")
                    for w in warnings:
                        ui.label(w.message).classes("text-sm hw-text-body whitespace-normal")
                    ui.label(
                        "Tip: 'Reset Node' re-derives this node from current code "
                        "(note: this discards any dynamically-added ports)."
                    ).classes("text-xs hw-text-dim whitespace-normal")
