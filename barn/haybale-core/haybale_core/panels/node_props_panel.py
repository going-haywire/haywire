# barn/haybale-studio/haybale_studio/panels/node_properties_panel.py
"""
NodePropertiesPanel — shows basic node identity information.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.ui.panel.decorator import panel
from haywire.ui.panel.base import BasePanel, PanelLayout
from haywire.ui.panel.render_utils import render_settings

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext


@panel(
    editors="properties",
    scopes="node",
    label="Node Properties",
    icon="info",
    default_open=False,
    order=10,
)
class NodePropertiesPanel(BasePanel):
    """Displays basic identity information for the selected node."""

    @classmethod
    def poll(cls, context: "SessionContext") -> bool:
        return context.active_node is not None

    def draw(self, context: "SessionContext", layout: PanelLayout) -> None:
        node = context.active_node
        if node is None:
            return
        try:
            label = node.node.identity.label if hasattr(node, "node") else str(node)
            cls_name = node.node.__class__.__name__ if hasattr(node, "node") else type(node).__name__
            node_id = getattr(node, "node_id", str(node))
        except Exception:
            label, cls_name, node_id = "?", "?", "?"
        layout.label(f"Name: {label}")
        layout.label(f"Class: {cls_name}")
        layout.label(f"ID: {node_id}")


@panel(
    registry_id="node_instance_settings",
    editors="properties",
    scopes="node",
    label="Node",
    icon="settings",
    order=20,
    default_open=True,
)
class NodeInstanceSettingsPanel(BasePanel):
    """Displays per-instance node settings (muted, collapsed, pinned, etc.)."""

    @classmethod
    def poll(cls, context: "SessionContext") -> bool:
        node = context.active_node
        return (
            node is not None
            and hasattr(node, "node")
            and node.node is not None
            and hasattr(node.node, "props")
        )

    def draw(self, context: "SessionContext", layout: PanelLayout) -> None:
        node_wrapper = context.active_node
        if node_wrapper is None:
            return
        render_settings(node_wrapper.node.props)
