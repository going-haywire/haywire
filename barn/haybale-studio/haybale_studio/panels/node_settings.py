# barn/haybale-studio/haybale_studio/panels/node_settings.py
"""
NodeSettingsPanel — renders all user-defined settings on the selected node.

Appears under the SettingsFocus, one collapsible section per bag.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


from haywire.ui import elements as hui
from haywire.ui.panel import Panel, PanelLayout
from haywire.ui.panel.decorator import panel

from haywire.ui.panel.render_utils import render_settings

from haybale_studio.editors.properties_editor_actions import PropertiesEditorActions
from haybale_studio.panels.focuses import SettingsFocus
from haybale_studio.state.edit_state import EditState

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext


@panel(
    action=PropertiesEditorActions,
    focus=SettingsFocus,
    label="Node Settings",
    icon=hui.icon.node_settings,
    order=10,
    default_open=True,
)
class NodeSettingsPanel(Panel):
    """Discovers and renders all user-defined settings on the selected node."""

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        node = ctx.data[EditState].active_node.value
        return (
            node is not None
            and hasattr(node, "node")
            and node.node is not None
            and bool(node.node.list_setting_bags())
        )

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: PropertiesEditorActions,
    ) -> None:
        node = ctx.data[EditState].active_node.value

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
