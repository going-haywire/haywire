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
        main_card.classes("node-card drag-handle zoom-pan-lod0").style(
            "background-color: var(--hw-node-bg); border-radius: 6px; "
            f"overflow: visible; padding: {_CARD_PADDING}px; min-width: 0;"
        )

        # Discover ports by PortType — the split action owns the IDs, not this skin.
        ports = node.ports.values()
        inlet = next((p for p in ports if p.port_type == PortType.INLET), None)
        outlet = next((p for p in ports if p.port_type == PortType.OUTLET), None)

        # Stack the two pins along the flow axis so they straddle opposite
        # edges. `overflow: visible` is repeated here because a pin offset past
        # the edge is clipped by the nearest ancestor lacking it, not just by
        # the card. No gap: the box should be the size of the dot.
        flow_axis = "column" if layout.is_vertical else "row"
        with main_card:
            with ui.element("div").style(
                f"display: flex; flex-direction: {flow_axis}; align-items: center; "
                "justify-content: center; gap: 0; flex-wrap: nowrap; overflow: visible;"
            ):
                if inlet is not None:
                    self._render_reroute_pin(inlet, wrapper.node_id, layout)
                if outlet is not None:
                    self._render_reroute_pin(outlet, wrapper.node_id, layout)

    def _render_reroute_pin(self, port, node_id: str, layout: LayoutDirection) -> None:
        render_pin(
            port,
            node_id,
            layout=layout,
            pin_gutter=_PIN_GUTTER,
            card_padding=_CARD_PADDING,
            pin_protrusion=_PIN_PROTRUSION,
        )
