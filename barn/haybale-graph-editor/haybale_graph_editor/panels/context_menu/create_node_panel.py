"""
CreateNodePanel — context menu panel for the canvas trigger.

actions: CanvasContextActions, focus=CanvasFocus.
Also hosts CanvasPasteSelectionPanel (paste in canvas context).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.ui.panel.focus import CanvasFocus
from haywire.core.node.info import NodeInfo
from haywire.ui import elements as hui
from haywire.core.session.signals import Reveal
from haywire.ui.panel import BasePanel
from haywire.ui.panel.layout import PanelLayout
from haywire.ui.panel.decorator import panel

from ...state.edit_state import EditState
from ...editors.graph_canvas.handlers.context_menu_actions import CanvasContextActions
from ...editors.graph_canvas.node_menu_builder import NodeMenuBuilder

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


@panel(
    actions=CanvasContextActions,
    focus=CanvasFocus,
    label="Create Node",
    icon=hui.icon.add,
    order=0,
)
class CreateNodePanel(BasePanel):
    """Render the hierarchical node-creation menu with search on canvas right-click."""

    actions: CanvasContextActions

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
            layout.label("No node factory available.")
            return

        def _on_node_selected(node_info: NodeInfo) -> None:
            self.actions.create_node_at_click(node_info.identity.registry_key)

        def _on_context_click(node_info: NodeInfo) -> None:
            if node_info.library is not None and ctx.app.library_manager.is_installed(node_info.library.id):
                # Assigning emits SessionContext.active_component synthetically.
                ctx.active_component = node_info.identity.registry_key

        with layout:
            builder = NodeMenuBuilder(
                node_factory,
                on_node_selected=_on_node_selected,
                on_context_click=_on_context_click,
            )
            builder.create_node_menu(recent_nodes=[], show_search=True)


@panel(
    actions=CanvasContextActions,
    focus=CanvasFocus,
    label="Paste",
    icon=hui.icon.paste,
    order=10,
)
class CanvasPasteSelectionPanel(BasePanel):
    """Paste panel in the canvas context.

    Companion to SelectionPasteSelectionPanel for the selection context.
    Both share the paste_at_click verb on their respective Protocols.
    """

    actions: CanvasContextActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.data[EditState].clipboard is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        layout.button(
            "Paste",
            icon=hui.icon.paste,
            on_click=self.actions.paste_at_click,
        )
