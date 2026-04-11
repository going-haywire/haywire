"""
CreateNodePanel — context menu panel for the canvas trigger.

Renders NodeMenuBuilder + search bar when the user right-clicks on empty
canvas space.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.core.node.info import NodeInfo
from haywire.ui import elements as hui
from haywire.ui.panel.base import BasePanel, PanelLayout
from haywire.ui.panel.decorator import panel
from haywire.ui.context_events import ContextChangedEvent, ContextChangeType
from haywire.ui.graph_canvas.event_definitions import NodeCreateRequestEvent
from haywire.ui.graph_canvas.node_menu_builder import NodeMenuBuilder

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext


@panel(
    editors="context_menu",
    scopes="canvas",
    label="Create Node",
    icon=hui.icon.add,
    order=0,
)
class CreateNodePanel(BasePanel):
    """Render the hierarchical node-creation menu with search on canvas right-click."""

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

        def _on_context_click(node_info: NodeInfo) -> None:
            if context.app.library_manager.is_installed(node_info.library.id):
                lib = context.app.library_manager.get_installed_library(node_info.library.id)
                registry_key = node_info.identity.registry_key
                context.active_component = {
                    "lib": lib,
                    "class_name": registry_key.split(":")[-1],
                    "comp_type": "nodes",
                    "registry_key": registry_key,
                }
                # Ensure the right area shows the ComponentDetailEditor.
                switch_right = context.metadata.get("switch_right_area")

                from haybale_studio.editors.library_component_editor import LibraryComponentEditor as cde
                if switch_right is not None:
                    try:
                        switch_right(cde.class_identity.registry_key)
                    except Exception:
                        pass

                context.session.notify_context_changed(
                    ContextChangedEvent(
                        change_type=ContextChangeType.ACTIVE_COMPONENT_CHANGED,
                        source_editor="library_detail"
                    )
                )

        with layout:
            builder = NodeMenuBuilder(node_factory)
            builder.create_node_menu(
                on_node_selected=_on_node_selected,
                on_context_click=_on_context_click,
                recent_nodes=recent_nodes,
                show_search=True,
            )
