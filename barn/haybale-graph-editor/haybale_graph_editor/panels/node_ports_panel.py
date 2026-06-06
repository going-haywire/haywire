# packages/haywire-core/src/haywire/ui/panels/node_ports_panel.py
"""
NodePortsPanel — lists inlet, outlet, and config ports on the selected node.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel, PanelLayout
from haywire.ui.panel.decorator import panel

from ..focuses import NodeFocus
from ..state.edit_state import EditState

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


@panel(
    focus=NodeFocus,
    label="Ports",
    icon=hui.icon.node_ports,
    default_open=False,
    order=20,
)
class NodePortsPanel(BasePanel):
    """Displays the inlet, outlet, and config ports of the selected node."""

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.data[EditState].active_node is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        node = ctx.data[EditState].active_node
        if node is None:
            return
        with layout:
            try:
                hw_node = node.node if hasattr(node, "node") else None
                if hw_node is None:
                    hui.label("No port data available")
                    return

                inlets = list(getattr(hw_node, "inlets", {}).values())
                outlets = list(getattr(hw_node, "outlets", {}).values())
                configs = [
                    p
                    for p in getattr(hw_node, "ports", {}).values()
                    if hasattr(p, "flow_type") and str(getattr(p.flow_type, "name", "")) == "NONE"
                ]

                hui.label(f"Inlets ({len(inlets)})")
                for port in inlets:
                    port_id = getattr(port, "port_id", "?")
                    port_type = getattr(port, "data_type", None)
                    type_name = port_type.__class__.__name__ if port_type else "?"
                    hui.label(f"  • {port_id}: {type_name}")

                hui.separator()
                hui.label(f"Outlets ({len(outlets)})")
                for port in outlets:
                    port_id = getattr(port, "port_id", "?")
                    port_type = getattr(port, "data_type", None)
                    type_name = port_type.__class__.__name__ if port_type else "?"
                    hui.label(f"  • {port_id}: {type_name}")

                if configs:
                    hui.separator()
                    hui.label(f"Config ({len(configs)})")
                    for port in configs:
                        port_id = getattr(port, "port_id", "?")
                        hui.label(f"  • {port_id}")

            except Exception:
                hui.label("Error reading ports")
