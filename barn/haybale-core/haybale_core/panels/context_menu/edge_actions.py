"""
Context menu panels for edge actions.

Contributed to editor='context_menu', scope='edge'.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.ui import elements as hui
from haywire.ui.panel.base import BasePanel, PanelLayout
from haywire.ui.panel.decorator import panel

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext


def _emit(context: "SessionContext", event):
    fn = context.metadata.get("on_emit_event")
    if fn:
        fn(event)


@panel(
    editors="context_menu",
    scopes="edge",
    label="Reconnect Edge",
    icon=hui.icon.edge,
    order=10,
)
class ReconnectEdgePanel(BasePanel):
    """
    Removes the edge and starts a new connection drag from the anchor pin.

    The anchor pin is the end *opposite* to where the user right-clicked:
    - atSinkEnd=True  → user clicked near inlet  → anchor is the outlet (source)
    - atSinkEnd=False → user clicked near outlet → anchor is the inlet (sink)
    """

    @classmethod
    def poll(cls, context: "SessionContext") -> bool:
        return context.active_edge is not None

    def draw(self, context: "SessionContext", layout: PanelLayout) -> None:
        from haywire.ui.graph_canvas.event_definitions import SyncEdgeReconnectEvent

        wrapper = context.active_edge
        edge_id = wrapper._edge_id
        at_sink_end = context.metadata.get("edge_reconnect_end", False)

        if at_sink_end:
            # Clicked near inlet → reconnect from outlet (source) side
            anchor_node_id = wrapper.source_node_id
            anchor_pin_id = wrapper.outlet_port_id
        else:
            # Clicked near outlet → reconnect from inlet (sink) side
            anchor_node_id = wrapper.sink_node_id
            anchor_pin_id = wrapper.inlet_port_id

        def _reconnect():
            _emit(
                context,
                SyncEdgeReconnectEvent(
                    edge_id=edge_id,
                    anchorNodeId=anchor_node_id,
                    anchorPinId=anchor_pin_id,
                ),
            )

        layout.button("Reconnect", icon=hui.icon.edge, on_click=_reconnect)
