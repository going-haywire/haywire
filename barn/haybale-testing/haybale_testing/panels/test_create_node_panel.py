"""
Test-only create-node panel for haybale_testing.

Uses editors="test_inspector", scopes="test_canvas" to avoid
clashing with the production editor/scope namespace.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.core.node.info import NodeInfo
from haywire.ui.panel.base import BasePanel, PanelLayout
from haywire.ui.panel.decorator import panel
from haywire.ui.graph_canvas.event_definitions import NodeCreateRequestEvent
from haywire.ui.graph_canvas.node_menu_builder import NodeMenuBuilder

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext


@panel(
    registry_id="test_create_node",
    editors="test_inspector",
    scopes="test_canvas",
    label="Create Node",
    icon="add",
    order=0,
)
class TestCreateNodePanel(BasePanel):
    """Test version of CreateNodePanel registered under test_inspector/test_canvas."""

    @classmethod
    def poll(cls, context: "SessionContext") -> bool:
        return True

    def draw(self, context: "SessionContext", layout: PanelLayout) -> None:
        node_factory = context.app.node_factory

        if node_factory is None:
            layout.label("No node factory available.")
            return

        on_emit_event = context.metadata.get("on_emit_event")
        recent_nodes = context.metadata.get("recent_nodes", [])
        canvas_position = context.metadata.get("canvas_position", {"x": 0.0, "y": 0.0})

        def _on_node_selected(node_info: NodeInfo) -> None:
            if on_emit_event:
                on_emit_event(
                    NodeCreateRequestEvent(
                        registryKey=node_info.identity.registry_key,
                        position=canvas_position,
                    )
                )

        builder = NodeMenuBuilder(node_factory)
        builder.create_node_menu(
            on_node_selected=_on_node_selected,
            recent_nodes=recent_nodes,
            show_search=True,
        )
