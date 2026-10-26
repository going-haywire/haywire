# barn/haybale-graph-editor/haybale_graph_editor/panels/properties/setting/node.py
"""
NodeSettingsPanel — renders all user-defined settings on the selected node.

Appears on SettingsInspector, one collapsible section per bag.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


from haywire.core.signals import (
    ActiveGraphMoved,
    GraphDataMutated,
    SelectionMoved,
)
from haywire.core.access import AccessTier
from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel, PanelLayout
from haywire.ui.panel.decorator import panel

from haywire.ui.panel.render_utils import render_settings

from haybale_graph_editor.panels._gating import is_reroute_node
from haybale_graph_editor.state.graph_app_state import route_for
from haybale_graph_editor.surfaces import SettingsInspector
from haybale_graph_editor.state.edit_state import EditState

if TYPE_CHECKING:
    from haywire.core.node.base import BaseNode
    from haywire.core.session.context import SessionContext
    from haywire.core.settings.settings import Settings


@panel(
    surface=SettingsInspector,
    requires=AccessTier.VIEW,
    label="Node Settings",
    description="Discovers and renders all user-defined settings on the selected node.",
    icon=hui.icon.node_properties,
    order=10,
    default_open=True,
    redraw_on=(SelectionMoved, GraphDataMutated, ActiveGraphMoved),
)
class NodeSettingsPanel(BasePanel):
    """Discovers and renders all user-defined settings on the selected node."""

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        node = ctx.data[EditState].active_node
        if is_reroute_node(ctx):
            return False
        return (
            node is not None
            and hasattr(node, "node")
            and node.node is not None
            and bool(_user_bags(node.node))
            and route_for(ctx) is not None
        )

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        node = ctx.data[EditState].active_node
        if node is None:
            return

        route = route_for(ctx)
        if route is None:
            return  # poll() checked it; a None route would draw the bag writable without the route
        with layout:
            for bag_name, bag in _user_bags(node.node).items():
                header = bag_name.replace("_", " ").title()
                with hui.category_group(header):
                    render_settings(ctx, bag, route=route)


def _user_bags(node: "BaseNode") -> "dict[str, Settings]":
    """Return the node's setting bags except ``props``, which ``NodePropertiesPanel`` renders."""
    return {name: bag for name, bag in node.list_setting_bags().items() if name != "props"}
