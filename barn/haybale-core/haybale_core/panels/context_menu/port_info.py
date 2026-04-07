"""
Context menu panel for port information.

Contributed to editor='context_menu', scope='port.info'.
Opened when the user right-clicks any pin on a node.
Replaces the old inline ui.tooltip() that was embedded in NodeSkin._render_pin.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.ui import elements as hui
from haywire.ui.panel.base import BasePanel, PanelLayout
from haywire.ui.panel.decorator import panel

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext


@panel(
    editors="context_menu",
    scopes="port.info",
    label="Port Info",
    icon=hui.icon.edge,
    order=10,
)
class PortInfoPanel(BasePanel):
    @classmethod
    def poll(cls, context: "SessionContext") -> bool:
        return context.active_port is not None

    def draw(self, context: "SessionContext", layout: PanelLayout) -> None:
        port = context.active_port
        with layout.container:
            hui.section_label(port.id)
            if port.description:
                hui.label(port.description)
            hui.info_label(f"Flow: {port.flow_type.value}")
            if hasattr(port, "_data"):
                type_key = port._data.get_stored_type().class_identity.registry_key
                hui.info_label(f"Type: {type_key}")
