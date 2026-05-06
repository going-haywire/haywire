"""
CreateNodePanel — context menu panel for the canvas trigger.

Phase 1.5: action=CanvasContextActions, focus=CanvasFocus.
Also hosts CanvasPasteSelectionPanel (paste in canvas context).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haybale_studio.focuses import CanvasFocus
from haywire.core.node.info import NodeInfo
from haywire.ui import elements as hui
from haywire.ui.context_signals import ActiveComponentMoved, Reveal
from haybale_studio.editors.graph_canvas.handlers.context_menu_actions import CanvasContextActions
from haybale_studio.editors.graph_canvas.node_menu_builder import NodeMenuBuilder
from haywire.ui.panel import Panel
from haywire.ui.panel.layout import PanelLayout
from haywire.ui.panel.decorator import panel

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext


@panel(
    action=CanvasContextActions,
    focus=CanvasFocus,
    label="Create Node",
    icon=hui.icon.add,
    order=0,
)
class CreateNodePanel(Panel):
    """Render the hierarchical node-creation menu with search on canvas right-click."""

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return True

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: CanvasContextActions,
    ) -> None:
        node_factory = ctx.app.node_factory
        if node_factory is None:
            layout.label("No node factory available.")
            return

        def _on_node_selected(node_info: NodeInfo) -> None:
            actions.create_node_at_click(node_info.identity.registry_key)

        def _on_context_click(node_info: NodeInfo) -> None:
            if ctx.app.library_manager.is_installed(node_info.library.id):
                from haybale_studio.editors.library_component_editor import LibraryComponentEditor

                ctx.active_component.value = node_info.identity.registry_key
                ctx.session.signal(ActiveComponentMoved())
                ctx.session.lifecycle(Reveal(editor=LibraryComponentEditor))

        with layout:
            builder = NodeMenuBuilder(
                node_factory,
                on_node_selected=_on_node_selected,
                on_context_click=_on_context_click,
            )
            builder.create_node_menu(recent_nodes=[], show_search=True)


@panel(
    action=CanvasContextActions,
    focus=CanvasFocus,
    label="Paste",
    icon=hui.icon.paste,
    order=10,
)
class CanvasPasteSelectionPanel(Panel):
    """Paste panel in the canvas context.

    Companion to SelectionPasteSelectionPanel for the selection context.
    Both share the paste_at_click verb on their respective Protocols.
    """

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.clipboard.value is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: CanvasContextActions,
    ) -> None:
        layout.button(
            "Paste",
            icon=hui.icon.paste,
            on_click=actions.paste_at_click,
        )
