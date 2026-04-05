# barn/haybale-studio/haybale_studio/panels/node_settings.py
"""
NodeSettingsPanel — renders all user-defined settings on the selected node.

Appears in the 'settings' scope (tune icon, order=65), one collapsible section per bag.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import ui

from haywire.ui import elements as hui
from haywire.ui.panel.decorator import panel
from haywire.ui.panel.base import BasePanel, PanelLayout

from haywire.ui.panel.render_utils import render_settings

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext


@panel(
    editors="properties",
    scopes="settings",
    label="Node Settings",
    icon=hui.icon.node_settings,
    order=10,
    default_open=True,
)
class NodeSettingsPanel(BasePanel):
    """Discovers and renders all user-defined settings on the selected node."""

    @classmethod
    def poll(cls, context: "SessionContext") -> bool:
        node = context.active_node
        return (
            node is not None
            and hasattr(node, "node")
            and node.node is not None
            and bool(node.node.list_setting_bags())
        )

    def draw(self, context: "SessionContext", layout: PanelLayout) -> None:
        node = context.active_node

        bags = node.node.list_setting_bags()
        if not bags:
            layout.label("No settings bags found.")
            return

        for bag_name, bag in bags.items():
            if bag_name == "props":
                continue  # skip props bag, rendered separately in NodePropertiesPanel
            header = bag_name.replace("_", " ").title()
            with hui.category_group(header):
                render_settings(bag)
