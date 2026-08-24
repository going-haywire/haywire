# barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/context/context.py
"""
The canvas right-click menu, as a small tree of surfaces.

``GraphContextPanel`` owns the arrangement — an icon shortcut row along the
top edge and a prime area below — and renders both region surfaces into the
*same* popup. It implements none of ``GraphActions`` itself
(``SessionContextMenuProvider`` does), so it **pipes**: ``render_surface``
passes ``self.actions`` down without being told, and a panel two levels below
reaches the provider without either panel naming it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import ui

from haywire.core.node.info import NodeInfo
from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel
from haywire.ui.panel.layout import PanelLayout
from haywire.ui.panel.decorator import panel

from .....surfaces import (
    GraphActions,
    GraphContext,
    GraphContextBody,
    GraphMoreActions,
    GraphToolBar,
)
from .....editors.graph_canvas.node_menu_builder import NodeMenuBuilder

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


@panel(
    surface=GraphContext,
    hosts=(GraphToolBar, GraphContextBody),
    label="Graph Context",
    icon=hui.icon.canvas,
    order=0,
)
class GraphContextPanel(BasePanel):
    """Layout-only root of the canvas menu: shortcut row, then prime area."""

    actions: GraphActions

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        with layout:
            with ui.row().classes("items-center gap-1"):
                self.render_surface(GraphToolBar, ctx)
            with ui.column().classes("w-full"):
                self.render_surface(GraphContextBody, ctx)


@panel(
    surface=GraphToolBar,
    label="Paste",
    icon=hui.icon.paste,
    order=10,
)
class PastePanel(BasePanel):
    """Paste at the click position, as an icon shortcut.

    Declares no ``poll``: the OS clipboard is not readable synchronously at
    poll time, so the shortcut is always shown and the handler reports
    "Nothing to paste". There is deliberately no ``ctx.app.clipboard``
    predicate to gate on.
    """

    actions: GraphActions

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        with layout:
            hui.icon_action(hui.icon.paste, tooltip="Paste", on_click=self.actions.paste_at_click)


@panel(
    surface=GraphToolBar,
    hosts=(GraphMoreActions,),
    label="More Actions",
    icon="more_horiz",
    order=999,
)
class GraphMorePanel(BasePanel):
    """The "…" — a panel that is itself a host.

    The provider travels one hop further by the pipe default, so a panel
    landing on ``GraphMoreActions`` reaches it through three hops without any
    of them being an inherited tree edge.

    An empty flyout greys this row retroactively: ``GraphMoreActions`` is an
    extension point, and its resting state is having nothing on it.
    """

    actions: GraphActions

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        with layout:
            with hui.flyout("more_horiz", tooltip="More actions"):
                self.render_surface(GraphMoreActions, ctx)


@panel(
    surface=GraphContextBody,
    label="Create Node",
    icon=hui.icon.add,
    order=0,
)
class CreateNodeMenuPanel(BasePanel):
    """The hierarchical node-creation menu, search and tree together.

    Kept whole in the prime area: ``NodeMenuBuilder`` couples search and tree
    through mutable element handles on one instance, so splitting them across
    two panels needs its own design. Moving the tree into the "…" flyout is a
    follow-up.
    """

    actions: GraphActions

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        node_factory = ctx.app.node_factory
        if node_factory is None:
            with layout:
                hui.error_label("No node factory available.")
            return

        def _on_node_selected(node_info: NodeInfo) -> None:
            self.actions.create_node_at_click(node_info.identity.registry_key)

        def _on_context_click(node_info: NodeInfo) -> None:
            if node_info.library is not None:
                # Assigning emits SessionContext.active_component synthetically.
                ctx.active_component = node_info.identity.registry_key

        with layout:
            builder = NodeMenuBuilder(
                node_factory,
                on_node_selected=_on_node_selected,
                on_context_click=_on_context_click,
            )
            builder.create_node_menu(recent_nodes=[], show_search=True)
