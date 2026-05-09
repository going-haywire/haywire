# barn/haybale-studio/haybale_studio/panels/node_properties_panel.py
"""
NodePropertiesPanel — shows basic node identity information.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel, PanelLayout
from haywire.ui.panel.decorator import panel
from haywire.ui.panel.render_utils import render_settings

from haybale_studio.focuses import NodeFocus
from haybale_studio.editors.properties_editor_actions import PropertiesEditorActions
from haybale_studio.state.edit_state import EditState

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


@panel(
    action=PropertiesEditorActions,
    focus=NodeFocus,
    label="Node Properties",
    icon=hui.icon.node_info,
    default_open=False,
    order=10,
)
class NodeInfoPanel(BasePanel):
    """Displays basic identity information for the selected node."""

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.data[EditState].active_node.value is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: PropertiesEditorActions,
    ) -> None:
        node = ctx.data[EditState].active_node.value
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
    action=PropertiesEditorActions,
    focus=NodeFocus,
    label="Node Properties",
    icon=hui.icon.node,
    order=20,
    default_open=True,
)
class NodePropertiesPanel(BasePanel):
    """Displays per-instance node settings (muted, collapsed, pinned, etc.)."""

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        node = ctx.data[EditState].active_node.value
        return (
            node is not None
            and hasattr(node, "node")
            and node.node is not None
            and hasattr(node.node, "props")
        )

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: PropertiesEditorActions,
    ) -> None:
        node_wrapper = ctx.data[EditState].active_node.value
        if node_wrapper is None:
            return
        render_settings(node_wrapper.node.props)
