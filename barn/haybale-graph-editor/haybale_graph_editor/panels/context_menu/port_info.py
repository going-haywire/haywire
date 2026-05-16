"""
PortInfoPanel — display-only panel showing port info on port right-click.

actions: PortContextActions (empty marker), focus=PortFocus.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel
from haywire.ui.panel.layout import PanelLayout
from haywire.ui.panel.decorator import panel

from ...focuses import PortFocus
from ...state.edit_state import EditState
from ...editors.graph_canvas.handlers.context_menu_actions import PortContextActions

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


@panel(
    actions=PortContextActions,
    focus=PortFocus,
    label="Port Info",
    icon=hui.icon.edge,
    order=10,
)
class PortInfoPanel(BasePanel):
    actions: PortContextActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.data[EditState].active_port is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        port = ctx.data[EditState].active_port
        if port is None:
            return
        with layout.container:
            hui.section_label(port.id)
            if port.description:
                hui.label(port.description)
            hui.info_label(f"Flow: {port.flow_type.value}")
            if hasattr(port, "_data"):
                type_key = port._data.get_stored_type().class_identity.registry_key
                hui.info_label(f"Type: {type_key}")
