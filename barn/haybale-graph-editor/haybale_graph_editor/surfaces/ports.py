"""Inspector surface listing the active node's ports."""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.ui.surface import Presentation, Surface

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


class PortInspector(Surface):
    """Properties tab listing the active node's ports."""

    id = "ports"
    order = 62
    # Icon matches NodePortsPanel's own (hui.icon.node_ports).
    presentation = Presentation(label="Ports", icon="device_hub")

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        from haybale_graph_editor.state.edit_state import EditState

        return ctx.data[EditState].active_node is not None
