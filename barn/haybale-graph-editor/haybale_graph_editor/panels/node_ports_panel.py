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
                    hui.empty_state("No port data available", icon=hui.icon.node_ports)
                    return

                inlets = list(getattr(hw_node, "inlets", {}).values())
                outlets = list(getattr(hw_node, "outlets", {}).values())
                configs = [
                    p
                    for p in getattr(hw_node, "ports", {}).values()
                    if hasattr(p, "flow_type") and str(getattr(p.flow_type, "name", "")) == "NONE"
                ]

                def _type_name(port: object) -> str:
                    port_type = getattr(port, "data_type", None)
                    return port_type.__class__.__name__ if port_type else "—"

                hui.section_label(f"Inlets ({len(inlets)})")
                for port in inlets:
                    hui.info_row(str(getattr(port, "port_id", "?")), _type_name(port))

                hui.section_label(f"Outlets ({len(outlets)})")
                for port in outlets:
                    hui.info_row(str(getattr(port, "port_id", "?")), _type_name(port))

                if configs:
                    hui.section_label(f"Config ({len(configs)})")
                    for port in configs:
                        hui.info_row(str(getattr(port, "port_id", "?")), _type_name(port))

            except Exception:
                hui.error_label("Error reading ports")
