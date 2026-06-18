"""Minimal skin for the reroute node — a tiny box with just two pins.

Renders only the reroute's inlet and outlet pin straddling a small inline box:
no label, no header, no widget, no resize handle. Subclasses ``BaseSkin``
directly (not ``NodeSkin``) so the graph-editor library stays host-agnostic —
it pulls in none of ``NodeSkin``'s layout settings, only the framework
``render_pin`` helper.

The reroute node binds itself to this skin in ``RerouteNode.post_init``.
"""

from __future__ import annotations

from nicegui import ui

from haywire.core.node.node_wrapper import NodeWrapper
from haywire.ui.skin.base import BaseSkin
from haywire.ui.skin.decorator import skin
from haywire.ui.skin.pin_render import render_pin

from ..nodes.reroute import REROUTE_INLET_ID, REROUTE_OUTLET_ID

# Tiny fixed geometry — a reroute is a dot on a wire, not a card.
_PIN_GUTTER = 18
_CARD_PADDING = 0
_PIN_PROTRUSION = 0


@skin(description="Minimal reroute skin — a tiny box with one inlet and one outlet pin.")
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

        inlet = node.ports.get(REROUTE_INLET_ID)
        outlet = node.ports.get(REROUTE_OUTLET_ID)

        with main_card:
            with ui.row().classes("items-center gap-1").style("flex-wrap: nowrap;"):
                # No tooltips: the reroute skin simply does not call
                # add_pin_tooltip (tooltips are decoupled from render_pin). The
                # right-click port menu IS wired (host concern, added here).
                if inlet is not None:
                    self._render_reroute_pin(inlet, wrapper.node_id, "left")
                if outlet is not None:
                    self._render_reroute_pin(outlet, wrapper.node_id, "right")

    def _render_reroute_pin(self, port, node_id: str, direction: str) -> None:
        pin_el = render_pin(
            port,
            node_id,
            direction=direction,
            pin_gutter=_PIN_GUTTER,
            card_padding=_CARD_PADDING,
            pin_protrusion=_PIN_PROTRUSION,
        )
