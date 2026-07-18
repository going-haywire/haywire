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
from haywire.core.types.enums import PortType
from haywire.ui.skin.base import BaseSkin
from haywire.ui.skin.decorator import skin
from haywire.ui.skin.pin_render import render_pin

# Tiny fixed geometry — a reroute is a dot on a wire, not a card.
_PIN_GUTTER = 18
_CARD_PADDING = 0
_PIN_PROTRUSION = 0


@skin(description="Minimal reroute skin — a tiny box with one inlet and one outlet pin.", hidden=True)
class RerouteSkin(BaseSkin):
    """Renders a reroute node as a small box with its two pins inline."""

    def render(self, main_card: ui.card, wrapper: NodeWrapper):
        node = wrapper.node

        # A small, label-less box. `node-card` + `drag-handle` + `zoom-pan-lod0`
        # keep it draggable and integrated with the canvas like any node card;
        # `overflow: visible` lets the pins straddle the edges.
        main_card.classes("node-card drag-handle zoom-pan-lod0").style(
            "background-color: var(--hw-node-bg); border-radius: 6px; "
            "overflow: visible; padding: 4px; min-width: 0;"
        )

        # Discover ports by PortType — the split action owns the IDs, not this skin.
        ports = node.ports.values()
        inlet = next((p for p in ports if p.port_type == PortType.INLET), None)
        outlet = next((p for p in ports if p.port_type == PortType.OUTLET), None)

        with main_card:
            with ui.row().classes("items-center gap-1").style("flex-wrap: nowrap;"):
                if inlet is not None:
                    self._render_reroute_pin(inlet, wrapper.node_id, "left")
                if outlet is not None:
                    self._render_reroute_pin(outlet, wrapper.node_id, "right")

    def _render_reroute_pin(self, port, node_id: str, direction: str) -> None:
        render_pin(
            port,
            node_id,
            direction=direction,
            pin_gutter=_PIN_GUTTER,
            card_padding=_CARD_PADDING,
            pin_protrusion=_PIN_PROTRUSION,
        )
