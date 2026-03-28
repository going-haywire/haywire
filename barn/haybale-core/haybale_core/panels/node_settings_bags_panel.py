# barn/haybale-studio/haybale_studio/panels/node_settings_bags_panel.py
"""
NodeSettingsBagsPanel — renders all user-defined settings bags on the selected node.

Appears in the 'settings' scope (tune icon, order=65), one collapsible section per bag.
"""

from nicegui import ui

from haywire.ui.panel.decorator import panel
from haywire.ui.panel.base import BasePanel, PanelLayout

from ._settings_panel_base import render_reactive

if False:  # TYPE_CHECKING
    from haywire.ui.context import SessionContext


@panel(
    registry_id="node_settings_bags",
    editor="properties",
    scope="settings",
    label="Node Settings",
    icon="tune",
    order=10,
    default_open=True,
)
class NodeSettingsBagsPanel(BasePanel):
    """Discovers and renders all user-defined settings bags on the selected node."""

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
        if node is None or not hasattr(node, "node") or node.node is None:
            return

        bags = node.node.list_setting_bags()
        if not bags:
            layout.label("No settings bags found.")
            return

        for bag_name, bag in bags.items():
            header = bag_name.replace("_", " ").title()
            with (
                ui.expansion(header, value=True)
                .classes("w-full")
                .props(
                    "dense dense-toggle"
                    ' header-class="text-xs font-bold hw-text-muted uppercase tracking-wide'
                    ' px-2 py-0 min-h-[24px]"'
                )
            ):
                render_reactive(bag)
