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
    """Base class for all NiceGui NodeSkin classes.

    SkinFactory caches ONE instance per registry key and reuses it across every
    node in every open graph, so a skin must hold no per-node render state —
    everything comes from the wrapper passed in on each call.

    Geometry is read live from ``NodeSkinSettings`` (which documents each
    field) through the upper-case properties below, so a settings change takes
    effect on the next render.
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

        Both declarations are load-bearing: the card must PAINT
        ``CARD_V_PADDING`` (``render_pin`` offsets every pin against it — paint
        something else and all pins seat off their edge identically, reading as
        a design choice rather than a bug), and ``position: relative`` makes
        the card the containing block for the pin strips.
        """
        v = self.CARD_V_PADDING
        return f"position: relative; padding-top: {v}px; padding-bottom: {v}px;"

    def layout_of(self, wrapper: NodeWrapper) -> LayoutDirection:
        """This node's layout direction.

        Never cache the result on ``self``: SkinFactory shares ONE skin
        instance across every node in every open graph.
        """
        return resolve_layout_direction(wrapper)

    def is_collapsed(self, wrapper: NodeWrapper) -> bool:
        """Whether THIS node's card is folded (ADR 0032, Node collapse).

        Reads ``node.props.collapsed``, whose mirror already resolves the
        graph < node chain. Degrades to unfolded rather than raising — this
        runs on the render path and must never take a node card down.

        Overridable so a skin can opt out of folding entirely (see
        ``ErrorNodeSkin.is_collapsed``) without duplicating the render
        branch that reads it. Never cache the result on ``self``, as with
        :meth:`layout_of`: ``SkinFactory`` shares ONE skin instance across
        every node in every open graph.
        """
        try:
            return bool(wrapper.node.props.collapsed)
        except Exception:
            return False

    def card_classes(self, wrapper: NodeWrapper) -> str:
        """Extra classes this skin's card carries — override to add a skin token.

        The shared ``w-full node-card zoom-pan-lod0`` are added by whoever
        builds the card, so they are never a subclass's to repeat.
        ``node-card`` is behavioural, not styling: canvas.vue keys the
        manual-resize clamp release off it.
        """
        return ""

    def _render_title(self, node) -> None:
        """The node's name in the header row. Override for an icon or a weight.

        An override must still draw ``node.display_label`` — this is the hook
        that lets every skin share one folded card. Draw ``display_label``, not
        ``identity.label``: it is the class label until the user names this
        instance in ``props.label``, and a skin reading the identity directly
        ignores that name with nothing on screen to say why.
        """
        ui.label(node.display_label).classes("text-h6 flex-grow")

    def _render_pin_column(
        self,
        ports: List[DataPort],
        wrapper: NodeWrapper,
        layout: LayoutDirection,
    ):
        """Stack bare pins on one card edge — the horizontal twin of a pin strip.

        Absolutely positioned, because ``render_pin`` seats a pin by pulling it
        off its STATIC position, which must therefore be the card's content
        edge. In flow it is not: the ghost pin and the row's 16px gap push the
        column ~28px inward, and every pin seats that far off its border.

        The containing block is the HEADER ROW (built by :meth:`header_row`),
        not the card — the row is full-bleed inside the card's padding, so its
        edge is that content edge, and pins stay on their own row instead of
        the card's vertical middle.

        Both the CSS side and the ``data-pin-dir-x/y`` vector come from
        ``layout`` inside ``_render_pin``, so they cannot drift apart.
        """
        if not ports:
            return
        edge = layout.side_for(ports[0])
        with (
            ui.column()
            .classes("gap-0 items-center")
            .style(f"position: absolute; {edge}: 0; top: 50%; transform: translateY(-50%);")
        ):
            for port in ports:
                self._render_pin(port, wrapper, layout=layout)

    def header_row(self, extra_classes: str = "") -> ui.row:
        """The card's header row — every skin's title goes here.

        Carries the ``position: relative`` that :meth:`_render_pin_column`
        anchors to. A hand-built header loses it silently: the pins fall back
        to the nearest positioned ancestor and seat off the border.
        """
        return (
            ui.row()
            .classes(f"drag-handle w-full items-center {extra_classes}".rstrip())
            .style("position: relative;")
        )

    def _render_collapsed(
        self,
        main_card: ui.card,
        node,
        wrapper: NodeWrapper,
        layout: LayoutDirection,
        card_style: str,
    ):
        """A folded card: the title, and its linked pins on the layout's edges.

        Shared by every skin — a folded card has no layout left to differ
        about beyond its orientation. A skin still owns its chrome via
        ``card_classes`` and :meth:`_render_title`.

        ``get_folded_ports`` returns only LINKED ports, so a 23-port node with
        two edges folds to two pins. That drop, not the missing labels, is the
        element-count win (ADR 0032). Group collapse is deliberately ignored: a
        port inside a folded group still needs a pin for its edge to land on.

        The diagnostics badge and root ghost pins are NOT optional — a folded
        node that hides its errors fails silently, and one without a ghost pin
        has no drop anchor, so an edge drag onto it does nothing.

        Width clamps are dropped: they size a label+widget column this card has
        no room for.

        **The card GROWS to seat its pins, and keeps its LayoutDirection.**
        Folding never re-sides a pin: a T2B node folds with inlets still on top
        and outlets still on the bottom, so its wires keep running the way the
        graph was laid out. That costs nothing at the edge layer — each pin
        emits its own ``data-pin-dir-x/y`` vector, so curves follow the sides.

        Both pin containers are absolutely positioned and so contribute NOTHING
        to the card's flow size. Whichever axis stacks the pins must therefore
        be reserved explicitly, or the stack spills past the border — which is
        not merely ugly: the edge layer anchors on each pin's rect, so a spilled
        pin's wires terminate outside the card too. Horizontally that is the
        header row's ``min-height`` (the taller of the two columns); vertically
        the strips already sit on the card's own top/bottom edges, and what
        needs reserving is the ``min-width`` the widest strip requires.
        """
        with main_card:
            self._render_diagnostics_badge(wrapper)

            linked = node.get_folded_ports()
            inlets = [p for p in linked if p.is_inlet()]
            outlets = [p for p in linked if not p.is_inlet()]

            if layout.is_vertical:
                self._render_collapsed_vertical(
                    main_card, node, wrapper, layout, card_style, inlets, outlets
                )
            else:
                self._render_collapsed_horizontal(
                    main_card, node, wrapper, layout, card_style, inlets, outlets
                )

    def _render_collapsed_horizontal(
        self,
        main_card: ui.card,
        node,
        wrapper: NodeWrapper,
        layout: LayoutDirection,
        card_style: str,
        inlets: List[DataPort],
        outlets: List[DataPort],
    ):
        """A folded L2R/R2L card: one row, a pin column pinned to each side.

        The row's ``min-height`` reserves the taller column, since both columns
        are out of flow. Counting per LIST rather than per side is safe only
        because ``max()`` is symmetric — the sides themselves swap under R2L,
        which :meth:`_render_pin_column` resolves from ``layout``.
        """
        main_card.classes(f"w-full node-card zoom-pan-lod0 {self.card_classes(wrapper)}").style(card_style)
        tallest = max(len(inlets), len(outlets))
        with self.header_row().style(f"min-height: {tallest * self.PIN_GUTTER}px;"):
            self._render_root_ghost_pins(wrapper, layout)
            self._render_pin_column(inlets, wrapper, layout)
            self._render_title(node)
            self._render_pin_column(outlets, wrapper, layout)

    def _render_collapsed_vertical(
        self,
        main_card: ui.card,
        node,
        wrapper: NodeWrapper,
        layout: LayoutDirection,
        card_style: str,
        inlets: List[DataPort],
        outlets: List[DataPort],
    ):
        """A folded T2B/B2T card: the title, between two edge pin strips.

        Structurally the unfolded vertical card minus its config band — the
        strips are placed by the same top-first rule, so folding moves nothing.
        ``vertical_card_style()`` is required for the same reason it is there:
        the strips offset against ``CARD_V_PADDING`` and anchor on the card,
        which must be the containing block.

        A strip lays its pins out in a ROW, so here the card must reserve
        WIDTH, not height. Each pin occupies ``PIN_GUTTER``; the ghost pin
        riding in each strip is why the widest strip is counted +1.
        """
        widest = max(len(inlets), len(outlets)) + 1
        main_card.classes(f"w-full node-card zoom-pan-lod0 {self.card_classes(wrapper)}").style(
            f"{card_style} {self.vertical_card_style()} min-width: {widest * self.PIN_GUTTER}px;"
        )

        # Whichever direction belongs on the card's TOP edge goes first — the
        # same rule the unfolded vertical card follows. A strip drawn at the
        # top while its pins are sided "bottom" offsets them INWARD.
        top_first = layout.inlet_side == "top"
        self.render_pin_strip(
            inlets if top_first else outlets,
            wrapper,
            layout,
            ghost_for=PortType.INLET if top_first else PortType.OUTLET,
        )
        with self.header_row():
            self._render_title(node)
        self.render_pin_strip(
            outlets if top_first else inlets,
            wrapper,
            layout,
            ghost_for=PortType.OUTLET if top_first else PortType.INLET,
        )

    def _render_diagnostics_badge(self, wrapper: NodeWrapper) -> List["HaywireException"]:
        """The unified error/warning badge. Drawn at EVERY rank, folded included.

        Never gated by detail, menu included: a node hiding the fact that it is
        broken is worse than a slow one. The menu body only costs elements on
        nodes that actually have diagnostics. The separate inline notice
        (:meth:`_render_alternates_notice`) is what canvas.vue's
        ``.hw-detail-diagnostic`` CSS rule hides below FULL.

        Returns the runtime errors so a caller can decide about that notice
        without re-reading node state.
        """
        runtime_errors = wrapper.state.get_errors() or []
        deprecation_str = wrapper.node.identity.deprecation_warning
        if runtime_errors or wrapper.state.has_warning() or deprecation_str:
            self._render_diagnostics_button(
                runtime_errors,
                wrapper.state.warnings,
                wrapper.node_id,
                deprecation_str=deprecation_str,
            )
        # The comment badge is the other always-drawn marker, and rides the
        # same call so no render path can pick up one and forget the other.
        self._render_comment_badge(wrapper)
        return runtime_errors

    def _render_alternates_notice(
        self,
        wrapper: NodeWrapper,
        runtime_errors: List["HaywireException"],
    ):
        """The inline "Alternate versions available" line — FULL only.

        The one piece of diagnostics detail that is genuinely inline; the
        badge's menu body is already behind a click.

        Always BUILT when there is something to say (2026-09 CSS-filter
        redesign). The ``.hw-detail-diagnostic`` class is unconditional;
        canvas.vue's ``[data-node-props-detail]`` rule hides it below FULL
        from the DOM attribute directly, so nothing needs consulting here any
        more to decide the class. ``runtime_errors`` and
        ``wrapper._alternate_registry_keys`` are real absence, not a rank
        gate, so they still guard construction.
        """
        if runtime_errors and wrapper._alternate_registry_keys:
            classes = "text-sm hw-text-warning mb-2 hw-detail-diagnostic"
            ui.label(f"Alternate versions available: {', '.join(wrapper._alternate_registry_keys)}").classes(
                classes
            )

    def render_port(
        self,
        port: DataPort,
        wrapper: NodeWrapper,
        widget_classes: str = "",
        layout: LayoutDirection | None = None,
    ):
        """Render a port according to its port type.

        Horizontal layouts only for inlets/outlets — vertically they belong in
        :meth:`render_pin_strip`, which has no room for the label/widget column
        this builds. Config ports are pinless and render the same either way.

        ``layout`` resolves from the wrapper when omitted; pass it when
        rendering many ports so the chain resolves once per card.
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
        """Render a port as `pin column | content`, or the mirror of it.

        ``side`` (``"left"``/``"right"``) flips the grid column order and which
        margin gets the tight ``CONTENT_GAP``, so the content inset matches
        either way. ``overflow: visible`` lets the pin straddle the card edge.

        The label and widget are always BUILT and unconditionally carry their
        ``.hw-detail-*`` class (2026-09 CSS-filter redesign) — canvas.vue's
        ``[data-node-props-detail]`` rule does the rank-based hiding from the
        DOM attribute directly, so nothing here needs to consult anything to
        decide what to build or which class to add.
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
                ui.label(port.label).classes("text-xs zoom-pan-lod2 hw-detail-label")
                if port.widget_key is not None and port.should_show_widget():
                    self.render_widget(port, wrapper.node_id, classes=f"{widget_classes} hw-detail-widget")

            # No tooltip on this content column. The port's own PIN carries it
            # (see _render_pin), and a second one here covers the label and the
            # widget too — a trigger area many times the pin's, firing a tooltip
            # wherever the pointer crosses the card body.

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

        No labels or widgets — tooltips carry the whole identification burden
        here. ``ghost_for`` adds this direction's root ghost pin; the strip IS
        the card edge, the only place a ghost's outward offset resolves.

        ``position: absolute`` is required, not cosmetic: in flow the strip
        reserves a full pin-row of empty space inside the card, and a negative
        margin cannot reclaim it because the card's ``row-gap`` still allocates
        a slot beside the flex item.

        Offsets resolve against the card's padding box (``top``/``bottom`` =
        ``CARD_V_PADDING``), putting each pin's static position exactly where
        it sat in flow so ``render_pin``'s offset lands it on the border. The
        explicit ``height`` keeps that true when only the smaller ghost pin is
        present.

        The card must be a containing block — see :meth:`vertical_card_style`;
        do not rely on Quasar's ``.q-card`` default.
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

    def _render_config(
        self,
        port,
        wrapper: NodeWrapper,
        widget_classes: str = "",
    ):
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
            ui.label(port.label).classes("text-xs zoom-pan-lod2 hw-detail-label")
            widget_el = None
            if port.widget_key is not None and port.should_show_widget():
                widget_el = self.render_widget(
                    port, wrapper.node_id, classes=f"{widget_classes} hw-detail-widget"
                )

        # A config port renders no pin, so the WIDGET is what the user points
        # at — not the whole row, which spans the label and the full card width
        # and would fire anywhere the pointer crosses the body. The tooltip is
        # HOSTED on the row (a widget is a custom Vue component with no
        # `<slot>`, so a child added to it never renders) and TRIGGERED by the
        # widget. A config with no widget gets none: nothing to aim at, and the
        # label already names it wherever it is shown.
        if widget_el is not None:
            add_pin_tooltip(config_row, port, trigger_el=widget_el)

    def _render_pin(
        self,
        pin: DataPort,
        wrapper: NodeWrapper,
        layout: LayoutDirection | None = None,
        cell_style: str = "",
    ):
        """Render a pin, supplying this skin's geometry to the framework helper.

        ``card_padding`` must be the padding on the axis this pin CROSSES —
        left/right for horizontal pins, top/bottom for vertical. The wrong one
        seats every pin slightly off its edge, identically on every node, which
        reads as a design choice rather than a bug.
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
            #
            # Unconditional since ADR 0032 retired `show_tooltips`: a bare pin
            # in a strip, on a folded card, or below LABELS has no label, so
            # the tooltip carries the whole identification burden.
            add_pin_tooltip(pin_el, pin)
            # PINS is the floor: linked ports only. An unlinked pin is always
            # BUILT (get_visible_ports() does not filter it out unfolded) but
            # carries this class so canvas.vue's [data-node-props-detail="pins"]
            # rule hides it, matching PINS_ALL and above.
            if not pin.is_linked():
                pin_el.classes("hw-detail-pins_all")

    def _render_root_ghost_pins(
        self,
        wrapper: NodeWrapper,
        layout: LayoutDirection | None = None,
        only: "PortType | None" = None,
    ):
        """Render inline ghost pins into the current flex context.

        Regular flex items, never absolutely positioned, so
        getBoundingClientRect() reports correct screen coordinates to the
        edge-drawing JS whatever the positioning context.

        Horizontally both sit in the header row, the outlet pushed last with
        ``order: 999``. Vertically the caller passes ``only=`` to place each in
        its matching edge strip — the strip IS the card edge, and a ghost left
        in a mid-card row offsets INTO the card instead of out to the border.

        Sides and vectors both come from LayoutDirection so they cannot drift.
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
            # takes render_pin's offset verbatim (the gutter half comes from
            # the 20px pins, not the ghost's own 12px box) — that puts every
            # pin on the strip on one edge line.
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

    def _render_comment_badge(self, wrapper: NodeWrapper) -> None:
        """A badge for the node's comment, if it has one. Hover to read it.

        Emptiness is the whole visibility rule (ADR 0032) — no companion flag.
        Drawn unconditionally so a note survives folding, where it matters
        most: a folded node is a box with a title.

        The tooltip is built eagerly, unlike a pin's, because there is at most
        one per node and only on nodes that have a comment.
        """
        try:
            comment = (wrapper.node.props.comment or "").strip()
        except Exception:
            return
        if not comment:
            return

        btn = ui.button(icon=hui.icon.message).props("flat dense round")
        btn.classes("text-xl px-2 py-1")
        # Left of the diagnostics badge, which sits at the same offset on the
        # right — so a node with both shows them side by side rather than
        # stacked on top of each other.
        btn.style("position: absolute; top: -25px; right: 32px;")
        btn.props(f'data-node-id="{wrapper.node_id}"')
        with btn:
            ui.tooltip(comment).classes("text-xs whitespace-normal").style("max-width: 22rem")

    def _render_diagnostics_button(
        self,
        errors: List["HaywireException"],
        warnings: List["NodeWarning"],
        node_id: str,
        deprecation_str: str = "",
    ) -> None:
        """Render a single badge unifying errors and advisory warnings.

        One icon and one count, coloured by highest severity: red for any
        runtime error, amber for advisory-only. Left-click opens the popup;
        right-click falls through to the selection context menu via
        ``data-node-id``.

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
