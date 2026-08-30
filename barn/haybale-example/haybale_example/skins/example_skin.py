from nicegui import ui
from haywire.core.node.node_wrapper import NodeWrapper
from haywire.core.node.base import BaseNode

from haywire.core.types.enums import LayoutDirection
from haywire.ui.skin.decorator import skin
from haywire.ui.skin.visibility import NodeVisibility

from haybale_studio.skins.node_skin import NodeSkin


@skin(description="Custom skin for nodes with special styling")
class ExampleNodeSkin(NodeSkin):
    """Custom skin for nodes with special styling.

    Two-band layout rather than the default skin's single stack: config ports
    span the full card width on top, then inlets and outlets sit side by side
    beneath. Ports are rendered through ``render_port``, which places each pin
    on the card edge its direction implies — so the left column's pins straddle
    the card's left border and the right column's its right.

    Configs get the full width precisely *because* they carry no pin: with no
    edge to attach to, nothing anchors them to a side, and their widgets are
    the ones that actually need room. Squeezing them into a third column made
    every config widget unusably narrow.
    """

    def render(self, main_card: ui.card, wrapper: NodeWrapper):
        node: BaseNode = wrapper.node
        node_id = f"example-node-{id(node)}"

        # Custom math-themed CSS.
        #
        # Deliberately NOT styled here: `.widget-container`. Inline-widget
        # SIZING belongs to the framework — canvas.vue declares a `max-height`
        # and `overflow` on that class with `!important`, so a skin's own rules
        # are silently outranked. Per-widget ceilings go on the widget, via
        # `@widget(max_height=)`.
        #
        # Nor is widget VISIBILITY a CSS question any more: a widget that
        # exists is visible, and whether it exists is `show.widget` below
        # (ADR 0032). This skin used to carry a `:hover` reveal here that never
        # once fired, back when the framework revealed on `.node-selected`.
        ui.add_head_html(f"""
        <style>
        .{node_id} .text-h6 {{
            color: #fbbf24;
            font-weight: bold;
        }}
        </style>
        """)
        # A skin with a look of its own, kept overridable.
        #
        # The skin's own values live in a SEPARATE token namespace
        # (--example-node-*) and reach the card as the FALLBACK argument of
        # var(). That ordering is the whole trick:
        #
        #   var(--hw-node-bg, <this skin's gradient>)
        #
        # …resolves to the gradient only while no tier has defined
        # --hw-node-bg for this card. The card is a CHILD of .ui-node-slot, so
        # defining --hw-node-bg on the card itself would shadow the very tiers
        # meant to override it — a skin that can never be restyled. Reading the
        # inherited value with a fallback inverts that correctly.
        #
        # `background`, not `background-color`: the value may be a gradient,
        # which is an <image>. See DefaultNodeSkin.
        main_card.style(
            "background: var(--hw-node-bg, linear-gradient(135deg, #667eea 0%, #764ba2 100%)); "
            "border: var(--hw-node-border-width, 3px) solid var(--hw-node-border-color, #4f46e5); "
            "border-radius: var(--hw-node-border-radius, 16px); "
            "color: var(--hw-node-text-color, white);"
        )

        # `node-card` is load-bearing, not cosmetic: canvas.vue keys the
        # manual-resize clamp release off it (`.ui-node-slot[data-size-adapt=
        # "manual*"] .node-card { max-width: none }`), and pan.vue restores
        # pointer-events/user-select through it. Without the class the card
        # stops growing at `max-w-sm` while the slot keeps expanding.
        # `math-node-card` is a sibling class, NOT a substitute.
        layout = self.layout_of(wrapper)
        show = self.show_of(wrapper)
        if show.collapsed:
            self._render_collapsed(main_card, node, wrapper, layout, node_id, show)
        elif layout.is_vertical:
            self._render_vertical(main_card, node, wrapper, layout, node_id, show)
        else:
            self._render_horizontal(main_card, node, wrapper, layout, node_id, show)

    def _render_collapsed(
        self,
        main_card: ui.card,
        node: BaseNode,
        wrapper: NodeWrapper,
        layout: LayoutDirection,
        node_id: str,
        show: NodeVisibility,
    ):
        """Folded: the header band, with linked pins flanking it.

        A folded card keeps the skin's identity — the icon and the themed
        border still say which skin drew it — but nothing else. ``show.ports``
        returns only LINKED ports, so an unwired node folds to a bare header
        and a wired one keeps exactly the pins its edges need.

        Vertical layouts fold to a horizontal one: a single row has no top or
        bottom edge for a pin to sit on, and a vertically-sided pin in a
        mid-card row offsets INWARD. ``_fold_layout`` on the default skin makes
        the same move for the same reason.
        """
        fold_layout = layout
        if layout.is_vertical:
            fold_layout = (
                LayoutDirection.LEFT_TO_RIGHT
                if layout.inlet_side == "top"
                else LayoutDirection.RIGHT_TO_LEFT
            )

        main_card.classes(f"w-full node-card zoom-pan-lod0 math-node-card {node_id}")

        with main_card:
            linked = show.ports(node)
            with ui.row().classes("drag-handle w-full items-center gap-2"):
                self._render_pin_stack([p for p in linked if p.is_inlet()], wrapper, fold_layout)
                ui.icon("calculate", color="yellow").classes("text-lg")
                ui.label("Math Node").classes("text-h6 flex-1")
                self._render_pin_stack([p for p in linked if not p.is_inlet()], wrapper, fold_layout)

    def _render_pin_stack(self, ports, wrapper: NodeWrapper, layout: LayoutDirection):
        """Bare pins in a column beside the title. Each pin's edge and direction
        vector both come from ``layout`` inside ``_render_pin``, so they cannot
        disagree."""
        if not ports:
            return
        with ui.column().classes("gap-0 items-center"):
            for port in ports:
                self._render_pin(port, wrapper, layout=layout)

    def _render_vertical(
        self,
        main_card: ui.card,
        node: BaseNode,
        wrapper: NodeWrapper,
        layout: LayoutDirection,
        node_id: str,
        show: NodeVisibility,
    ):
        """Vertical layouts (T2B / B2T): inlets/outlets become pin strips on
        the card's top/bottom edges; only configs stay in the body.
        """
        # `min-w-64`/`max-w-sm` size a label+widget content column that a
        # vertical card does not have.
        main_card.classes(f"w-full node-card zoom-pan-lod0 math-node-card {node_id}").style(
            self.vertical_card_style()
        )

        with main_card:
            ports = show.ports(node)
            configs = [port for port in ports if port.is_config()]
            inlets = [port for port in ports if port.is_inlet()]
            outlets = [port for port in ports if port.is_outlet()]

            # Whichever direction belongs on the card's TOP edge goes first —
            # inlets under T2B, outlets under B2T. Rendering a strip at the top
            # of the card while its pins are sided "bottom" would offset them
            # DOWN, i.e. inward.
            top_first = layout.inlet_side == "top"
            self.render_pin_strip(inlets if top_first else outlets, wrapper, layout)

            # Math-themed header
            with ui.row().classes("w-full items-center gap-2"):
                ui.icon("calculate", color="yellow").classes("text-lg")
                ui.label("Math Node").classes("text-h6 flex-1")

            # Configs, spanning the whole card. `_render_config` already lays
            # each row out at `width: 100%`, so the band takes whatever width
            # the card has.
            #
            # The band's own heading follows `show.label` like any other label:
            # a skin's chrome is not exempt from the rank it was handed, and
            # below FULL a heading over unlabelled rows names nothing.
            if configs:
                with ui.column().classes("w-full gap-1"):
                    if show.label:
                        ui.label("Config").classes("font-bold text-sm")
                    for port in configs:
                        self.render_port(port, wrapper, layout=layout, show=show)

            self.render_pin_strip(outlets if top_first else inlets, wrapper, layout)

    def _render_horizontal(
        self,
        main_card: ui.card,
        node: BaseNode,
        wrapper: NodeWrapper,
        layout: LayoutDirection,
        node_id: str,
        show: NodeVisibility,
    ):
        """Horizontal layouts (L2R / R2L): configs span the top, inlets and
        outlets sit side by side beneath.
        """
        main_card.classes(f"w-full min-w-64 max-w-sm node-card zoom-pan-lod0 math-node-card {node_id}")

        with main_card:
            ports = show.ports(node)
            configs = [port for port in ports if port.is_config()]
            inlets = [port for port in ports if port.is_inlet()]
            outlets = [port for port in ports if port.is_outlet()]

            # Math-themed header
            with ui.row().classes("w-full items-center gap-2"):
                ui.icon("calculate", color="yellow").classes("text-lg")
                ui.label("Math Node").classes("text-h6 flex-1")

            # Configs first, spanning the whole card. `_render_config` already
            # lays each row out at `width: 100%`, so the band takes whatever
            # width the card has. Pinless ports have no edge to move to.
            if configs:
                with ui.column().classes("w-full gap-1"):
                    if show.label:
                        ui.label("Config").classes("font-bold text-sm")
                    for port in configs:
                        self.render_port(port, wrapper, layout=layout, show=show)

            # Inlets and outlets side by side beneath. An empty column is
            # omitted rather than rendered blank, so an outlet-only node keeps
            # its pins on the card's outer edge. `min-w-0` lets each flex
            # column shrink below its content width — without it the columns
            # fight over the card and the pins drift off the border.
            #
            # Column ORDER follows the flow direction: the inlet column is
            # whichever side inlets' pins protrude from. Flipping only the
            # pins would strand each pin on the far side of its own label,
            # with edges crossing back over the card to reach the column
            # their labels live in.
            columns = (("Inputs", inlets), ("Outputs", outlets))
            if layout.inlet_side == "right":
                columns = columns[::-1]
            if inlets or outlets:
                with ui.row().classes("w-full gap-2"):
                    for heading, group in columns:
                        if not group:
                            continue
                        with ui.column().classes("flex-1 gap-1 min-w-0"):
                            if show.label:
                                ui.label(heading).classes("font-bold text-sm")
                            for port in group:
                                self.render_port(port, wrapper, layout=layout, show=show)
