"""Rail skin for the two boundary nodes — a narrow strip of pins with labels.

A boundary node is the edge of the Subgraph, not a card inside it, so it renders
as a rail: a slim strip carrying one labelled pin per port and no header, widget
or resize handle. Subclasses ``BaseSkin`` directly (not ``NodeSkin``) so the
layout carries no surplus settings and the module stays loadable from the
framework-owned builtin library.

The boundary nodes bind themselves to this skin by registry-key string on their
own ``props`` bag. This skin never imports either node class; it discovers its
ports by ``PortType`` introspection, so the port ids remain an implementation
detail of the collapse action.
"""

from __future__ import annotations

from nicegui import ui

from haywire.core.node.node_wrapper import NodeWrapper
from haywire.core.types.enums import LayoutDirection
from haywire.core.types.port import DataPort
from haywire.ui.skin.base import BaseSkin
from haywire.ui.skin.decorator import skin
from haywire.ui.skin.pin_render import (
    add_pin_tooltip,
    render_ghost_pin,
    render_pin,
    resolve_graph_layout_direction,
)

_PIN_GUTTER = 18
_PIN_PROTRUSION = 0
#: Ghost pin box, which render_ghost_pin draws. Smaller than a real pin, so its
#: offset is computed from this rather than from the gutter.
_GHOST_SIZE = 12
# Must match the padding the card PAINTS below: render_pin offsets pins against
# it, so a value the card does not paint seats every pin off its edge by the
# difference.
_CARD_PADDING = 4


@skin(
    label="Subgraph I/O",
    description="Rail skin for Subgraph Input and Output nodes — one labelled pin per port.",
    hidden=True,
)
class SubgraphIOSkin(BaseSkin):
    """Renders a boundary node as a rail of labelled pins along one card edge."""

    def render(self, main_card: ui.card, wrapper: NodeWrapper):
        node = wrapper.node

        # A boundary node is the edge of its Subgraph, so it follows the GRAPH's
        # layout direction: a per-node override would aim the rail away from the
        # nodes it feeds.
        layout = resolve_graph_layout_direction(wrapper)

        # `node-card` + `drag-handle` + `zoom-pan-lod0` keep the rail draggable
        # and integrated with the canvas like any node card; `overflow: visible`
        # lets the pins straddle the edge.
        #
        # `background`, not `background-color`: --hw-node-bg may hold a gradient,
        # which is an <image> and makes a `background-color` declaration invalid
        # — the card would lose its colour entirely rather than fall back.
        main_card.classes("node-card drag-handle zoom-pan-lod0").style(
            "background: var(--hw-node-bg); "
            "border: var(--hw-node-border-width) solid var(--hw-node-border-color); "
            "border-radius: var(--hw-node-border-radius); "
            "color: var(--hw-node-text-color); "
            f"overflow: visible; padding: {_CARD_PADDING}px; min-width: 0; gap: 2px;"
        )

        # Discover ports by direction — the collapse action owns the IDs.
        ports = [p for p in node.get_visible_ports() if p.has_pin()]

        with main_card:
            for port in ports:
                self._render_rail_row(port, wrapper.node_id, layout)
            # An edge whose port was removed falls back to the ghost, so the
            # wire stays on the card instead of hanging in space.
            self._render_ghosts(wrapper.node_id, layout, ports)

    def _render_ghosts(self, node_id: str, layout: LayoutDirection, ports: list[DataPort]) -> None:
        """Render the root ghost pins, one per side this rail actually uses.

        A boundary node faces one way, so only the side its ports sit on can
        receive a fallback edge. Rendered in a row of their own at the card's
        end, where the outward offset resolves against the card edge.
        """
        sides = {port.is_inlet() for port in ports}
        if not sides:
            return
        for is_inlet in sorted(sides, reverse=True):
            # One row each, so the ghost is the only item on its line and its
            # static position is the card's content edge — the same place a
            # real pin's row puts it. The offset is the ghost's own half-box,
            # not the pin gutter's: the two boxes differ in size.
            with ui.row().classes("items-center flex-nowrap w-full").style("min-width: 0;"):
                if not is_inlet:
                    # An outlet's offset resolves against the row's far edge,
                    # which a lone item only reaches when pushed there.
                    ui.element("div").style("flex: 1 1 auto; min-width: 0;")
                render_ghost_pin(
                    node_id,
                    layout=layout,
                    is_inlet=is_inlet,
                    offset=_CARD_PADDING + _GHOST_SIZE // 2 + _PIN_PROTRUSION,
                )

    def _render_rail_row(self, port: DataPort, node_id: str, layout: LayoutDirection) -> None:
        """Render one port as a full-width row with its pin on the card edge.

        The row carries no padding of its own on the pin's axis: a pin's offset
        assumes its row starts at the card edge, so indenting the row would
        inset the pin from the border.
        """
        # The label sits away from the pin's edge, so the rail reads in the
        # flow direction whichever way the graph runs.
        label_first = layout.side_for(port) in ("right", "bottom")
        row_cls = "items-center gap-1 flex-nowrap w-full"
        with ui.row().classes(row_cls).style("min-width: 0;"):
            if label_first:
                self._render_label(port)
            pin_el = render_pin(
                port,
                node_id,
                layout=layout,
                pin_gutter=_PIN_GUTTER,
                card_padding=_CARD_PADDING,
                pin_protrusion=_PIN_PROTRUSION,
                pin_icons=self.pin_icons,
            )
            if pin_el is not None:
                add_pin_tooltip(pin_el, port)
            if not label_first:
                self._render_label(port)

    def _render_label(self, port: DataPort) -> None:
        ui.label(port.label or port.id).classes("text-xs hw-text-muted truncate").style("min-width: 0;")
