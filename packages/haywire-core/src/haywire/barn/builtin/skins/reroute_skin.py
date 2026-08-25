"""Minimal skin for the reroute node — a tiny box with just two pins.

Renders only the reroute's inlet and outlet pin straddling a small inline box:
no label, no header, no widget, no resize handle. Subclasses ``BaseSkin``
directly (not ``NodeSkin``) so the layout carries no surplus settings.

The reroute node binds itself to this skin by registry-key string in
``RerouteNode.post_init``. This skin never imports the node class; it
discovers its ports by ``PortType`` introspection so the port ids remain
an implementation detail of ``SplitEdgeWithRerouteAction``.
"""

from __future__ import annotations

from nicegui import ui

from haywire.core.node.node_wrapper import NodeWrapper
from haywire.core.types.enums import LayoutDirection, PortType
from haywire.ui.skin.base import BaseSkin
from haywire.ui.skin.decorator import skin
from haywire.ui.skin.pin_render import render_pin, resolve_graph_layout_direction

# Tiny fixed geometry — a reroute is a dot on a wire, not a card.
_PIN_GUTTER = 18
_PIN_PROTRUSION = 0
# Must match the padding the card PAINTS below: render_pin offsets pins against
# it, so a value the card does not paint seats every pin off its edge by the
# difference. Was 0 against a painted 4px.
_CARD_PADDING = 4


@skin(description="Minimal reroute skin — a tiny box with one inlet and one outlet pin.", hidden=True)
class RerouteSkin(BaseSkin):
    """Renders a reroute node as a small box with its two pins inline."""

    def render(self, main_card: ui.card, wrapper: NodeWrapper):
        node = wrapper.node

        # A reroute is a dot on a wire, so it follows the GRAPH's layout
        # direction rather than its own node prop — a per-node override on a
        # reroute would point it away from the wire it sits on.
        layout = resolve_graph_layout_direction(wrapper)

        # A small, label-less box. `node-card` + `drag-handle` + `zoom-pan-lod0`
        # keep it draggable and integrated with the canvas like any node card;
        # `overflow: visible` lets the pins straddle the edges.
        #
        # `position: relative` makes the card the containing block for the two
        # absolutely-positioned pins below — a reroute can be manually resized,
        # and only positioning against the card's own padding box keeps the pins
        # on its borders at every size (Quasar's .q-card does not guarantee it).
        # `background`, not `background-color`: --hw-node-bg may hold a gradient
        # (a theme or a per-node override), which is an <image> and makes a
        # `background-color` declaration invalid — the card would silently lose
        # its colour entirely rather than fall back to anything.
        #
        # The radius is deliberately NOT --hw-node-border-radius: a reroute is a
        # small fixed dot, and a theme's card radius would swallow it.
        main_card.classes("node-card drag-handle zoom-pan-lod0").style(
            "background: var(--hw-node-bg); border-radius: 6px; position: relative; "
            f"overflow: visible; padding: {_CARD_PADDING}px; min-width: 0;"
        )

        # Discover ports by PortType — the split action owns the IDs, not this skin.
        ports = node.ports.values()
        inlet = next((p for p in ports if p.port_type == PortType.INLET), None)
        outlet = next((p for p in ports if p.port_type == PortType.OUTLET), None)

        # The card's intrinsic size — and therefore the floor the resize gadget
        # measures — comes from its in-flow content, and the pins below are all
        # absolute. Without this spacer the box would collapse to bare padding.
        # It reproduces the size the pins had when they sat in flow: the two
        # gutters end-to-end along the flow axis, one across it.
        span = _PIN_GUTTER * len([p for p in (inlet, outlet) if p is not None])
        box_w, box_h = (_PIN_GUTTER, span) if layout.is_vertical else (span, _PIN_GUTTER)
        with main_card:
            ui.element("div").style(f"width: {box_w}px; height: {box_h}px; flex: 0 0 auto;")

        # Each pin gets its OWN absolutely-positioned wrapper pinned to the card
        # edge it belongs on, rather than both sharing one centered flex row.
        # A reroute is resizable, and an in-flow row only lands the pins on the
        # borders while the card is at its intrinsic dot size: grow the card and
        # the row stays centered, leaving both pins floating in the middle.
        #
        # Which edge comes from `LayoutDirection` alone, so it flips with the
        # flow (R2L/B2T) exactly as the pin's own offset and direction vector do
        # — no inlet-first ordering assumption that the sides could contradict.
        #
        # The wrapper is positioned against the card's PADDING box (offset by
        # `_CARD_PADDING`), which puts each pin's static position exactly where
        # it sat in flow, so `render_pin`'s `card_padding + gutter//2 +
        # protrusion` offset still lands it on the border unchanged.
        # `overflow: visible` is repeated because a pin pushed past the edge is
        # clipped by the nearest ancestor lacking it, not just by the card.
        for pin in (inlet, outlet):
            if pin is None:
                continue
            edge = layout.side_for(pin)
            # Center on the cross axis: the pin tracks the middle of the border
            # it sits on however far that border grows.
            if layout.is_vertical:
                cross = "left: 0; right: 0; justify-content: center;"
            else:
                cross = "top: 0; bottom: 0; align-items: center;"
            with main_card:
                with ui.element("div").style(
                    "position: absolute; display: flex; overflow: visible; "
                    f"{cross} {edge}: {_CARD_PADDING}px;"
                ):
                    self._render_reroute_pin(pin, wrapper.node_id, layout)

    def _render_reroute_pin(self, port, node_id: str, layout: LayoutDirection) -> None:
        render_pin(
            port,
            node_id,
            layout=layout,
            pin_gutter=_PIN_GUTTER,
            card_padding=_CARD_PADDING,
            pin_protrusion=_PIN_PROTRUSION,
        )
