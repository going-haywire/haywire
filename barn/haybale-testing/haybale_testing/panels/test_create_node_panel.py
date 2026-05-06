"""Test fixture: TestCreateNodePanel."""

from __future__ import annotations

from typing import TYPE_CHECKING

from haybale_testing.test_actions import TestCanvasContextActions
from haybale_testing.test_focuses import TestCanvasFocus
from haywire.core.node.info import NodeInfo
from haywire.ui import elements as hui
from haywire.ui.graph_canvas.node_menu_builder import NodeMenuBuilder
from haywire.ui.panel import Panel
from haywire.ui.panel.layout import PanelLayout
from haywire.ui.panel.decorator import panel

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext


@panel(
    action=TestCanvasContextActions,
    focus=TestCanvasFocus,
    label="Create Node",
    icon=hui.icon.add,
    order=0,
)
class TestCreateNodePanel(Panel):
    """Test version of CreateNodePanel using TestCanvasContextActions / TestCanvasFocus."""

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return True

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: TestCanvasContextActions,
    ) -> None:
        node_factory = ctx.app.node_factory

        if node_factory is None:
            layout.label("No node factory available.")
            return

        def _on_node_selected(node_info: NodeInfo) -> None:
            actions.test_create_node_at_click(node_info.identity.registry_key)

        builder = NodeMenuBuilder(node_factory, on_node_selected=_on_node_selected)
        builder.create_node_menu(recent_nodes=[], show_search=True)
