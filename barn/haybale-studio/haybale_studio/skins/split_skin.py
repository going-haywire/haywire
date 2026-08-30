"""
Split NodeSkin — configs on top, inlets and outlets side by side

The counterpart to :class:`StackedNodeSkin`: same ports, two bands instead of
one column.
"""

from nicegui import ui

from haywire.core.node.node_wrapper import NodeWrapper
from haywire.core.node.base import BaseNode

from haywire.core.types.enums import LayoutDirection
from haywire.ui.skin.decorator import skin
from haywire.ui.skin.visibility import NodeVisibility

from .node_skin import NodeSkin


@skin(
    label="Split",
    description="Configs across the top, inlets and outlets in columns side by side",
)
class SplitNodeSkin(NodeSkin):
    """Two-band skin: configs span the card, inlets and outlets split beneath.

    Named for that split. Where :class:`StackedNodeSkin` puts every port type
    in one column, this gives config ports the full card width on top and then
    sets inlets and outlets side by side underneath. Ports are rendered through
    ``render_port``, which places each pin on the card edge its direction
    implies — so the left column's pins straddle the card's left border and the
    right column's its right.

    Configs get the full width precisely *because* they carry no pin: with no
    edge to attach to, nothing anchors them to a side, and their widgets are
    the ones that actually need room. Squeezing them into a third column made
    every config widget unusably narrow.

    Groups are not rendered as a hierarchy here — a two-column split has no
    place to put an indented, collapsible subtree without one column growing
    past the other. Use the stacked skin on nodes whose ports are grouped.
    """

    def card_classes(self, wrapper: NodeWrapper) -> str:
        """The split card's own token, alongside the shared ``node-card``.

        A sibling class, NOT a substitute: CSS class selectors match whole
        tokens, so a card carrying only this one would miss every `.node-card`
        rule — including the manual-resize clamp release keyed off it in
        canvas.vue.
        """
        return "split-node-card"

    def render(self, main_card: ui.card, wrapper: NodeWrapper):
        node: BaseNode = wrapper.node
        layout = self.layout_of(wrapper)
        show = self.show_of(wrapper)

        padding = self.CARD_H_PADDING
        # Pure var() consumption, same as the stacked skin: the look belongs to
        # the theme tier, not to the skin. A skin that hardcodes its palette
        # cannot be restyled by a @theme(theme_type='node') class.
        #
        # `background`, not `background-color`: a token may hold a gradient,
        # which is an <image> and so is dropped wholesale by the -color
        # longhand.
        card_style = (
            "background: var(--hw-node-bg); "
            "border: var(--hw-node-border-width) solid var(--hw-node-border-color); "
            "border-radius: var(--hw-node-border-radius); "
            "color: var(--hw-node-text-color); "
            f"backdrop-filter: blur(10px); "
            f"overflow: visible; padding-left: {padding}px; padding-right: {padding}px;"
        )

        if show.collapsed:
            # Folded, this card is the shared header row — see NodeSkin. The
            # two bands have nothing to say about a single row, so there is no
            # split-specific fold path.
            self._render_collapsed(main_card, node, wrapper, layout, card_style, show)
        elif layout.is_vertical:
            self._render_vertical(main_card, node, wrapper, layout, card_style, show)
        else:
            self._render_horizontal(main_card, node, wrapper, layout, card_style, show)

    def _render_vertical(
        self,
        main_card: ui.card,
        node: BaseNode,
        wrapper: NodeWrapper,
        layout: LayoutDirection,
        card_style: str,
        show: NodeVisibility,
    ):
        """Vertical layouts (T2B / B2T): inlets/outlets become pin strips on
        the card's top/bottom edges; only configs stay in the body.

        The two-band split has nothing left to express here — with both pin
        directions on the card edges, the body holds configs and nothing else,
        exactly as in the stacked skin. What survives is the config band's own
        heading.
        """
        # `min-w-64`/`max-w-sm` size a label+widget content column that a
        # vertical card does not have.
        main_card.classes(f"w-full node-card zoom-pan-lod0 {self.card_classes(wrapper)}").style(
            f"{card_style} {self.vertical_card_style()}"
        )

        with main_card:
            runtime_errors = self._render_diagnostics_badge(wrapper)

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

            with ui.row().classes("drag-handle w-full items-center gap-2"):
                self._render_title(node)
                self._render_alternates_notice(wrapper, runtime_errors, show)

            self._render_config_band(configs, wrapper, layout, show)

            self.render_pin_strip(outlets if top_first else inlets, wrapper, layout)

    def _render_horizontal(
        self,
        main_card: ui.card,
        node: BaseNode,
        wrapper: NodeWrapper,
        layout: LayoutDirection,
        card_style: str,
        show: NodeVisibility,
    ):
        """Horizontal layouts (L2R / R2L): configs span the top, inlets and
        outlets sit side by side beneath.
        """
        main_card.classes(
            f"w-full min-w-64 max-w-sm node-card zoom-pan-lod0 {self.card_classes(wrapper)}"
        ).style(card_style)

        with main_card:
            runtime_errors = self._render_diagnostics_badge(wrapper)

            ports = show.ports(node)
            configs = [port for port in ports if port.is_config()]
            inlets = [port for port in ports if port.is_inlet()]
            outlets = [port for port in ports if port.is_outlet()]

            with self.header_row("gap-2"):
                # Root ghost pins — always-present fallback connection anchors,
                # sided by the layout direction. Horizontally they belong in the
                # header row, where they are ordinary flex items.
                self._render_root_ghost_pins(wrapper, layout)

                # Ordinary pins for ports a collapsed group hides but an edge
                # still lands on. This skin renders no group hierarchy, but a
                # node can still arrive with groups collapsed from another skin,
                # and a linked port with no pin strands its edge.
                self._render_pin_column(node.get_hidden_connected_ports(is_inlet=True), wrapper, layout)

                self._render_title(node)

                self._render_pin_column(node.get_hidden_connected_ports(is_inlet=False), wrapper, layout)

                self._render_alternates_notice(wrapper, runtime_errors, show)

            self._render_config_band(configs, wrapper, layout, show)

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

    def _render_config_band(
        self,
        configs,
        wrapper: NodeWrapper,
        layout: LayoutDirection,
        show: NodeVisibility,
    ):
        """Configs, spanning the whole card.

        ``_render_config`` already lays each row out at `width: 100%`, so the
        band takes whatever width the card has.

        The band's own heading follows `show.label` like any other label: a
        skin's chrome is not exempt from the rank it was handed, and below FULL
        a heading over unlabelled rows names nothing.
        """
        if not configs:
            return
        with ui.column().classes("w-full gap-1"):
            if show.label:
                ui.label("Config").classes("font-bold text-sm")
            for port in configs:
                self.render_port(port, wrapper, layout=layout, show=show)
