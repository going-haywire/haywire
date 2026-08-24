"""Test fixture panels: TestCreateNodeMenuPanel, TestSessionStateMenuPanel."""

from __future__ import annotations

from typing import TYPE_CHECKING

from haybale_graph_editor.editors.graph_canvas.node_menu_builder import NodeMenuBuilder
from haybale_testing.state import TestSessionState
from haybale_testing.surfaces import TestCanvasActions, TestCanvasMenu
from haywire.core.node.info import NodeInfo
from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel
from haywire.ui.panel.decorator import panel
from haywire.ui.panel.layout import PanelLayout

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


@panel(
    surface=TestCanvasMenu,
    label="Create Node",
    icon=hui.icon.add,
    order=0,
)
class TestCreateNodeMenuPanel(BasePanel):
    """Test version of CreateNodeMenuPanel on the TestCanvasMenu surface."""

    actions: TestCanvasActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return True

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        node_factory = ctx.app.node_factory

        if node_factory is None:
            with layout:
                hui.label("No node factory available.")
            return

        def _on_node_selected(node_info: NodeInfo) -> None:
            self.actions.test_create_node_at_click(node_info.identity.registry_key)

        with layout:
            builder = NodeMenuBuilder(node_factory, on_node_selected=_on_node_selected)
            builder.create_node_menu(recent_nodes=[], show_search=True)


@panel(
    surface=TestCanvasMenu,
    label="Test SessionState Panel",
    order=99,
)
class TestSessionStateMenuPanel(BasePanel):
    """Reads TestSessionState.counter — exists to anchor the eager import."""

    actions: TestCanvasActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.data[TestSessionState].counter is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        counter = ctx.data[TestSessionState].counter
        with layout:
            hui.label(f"counter: {counter}")
