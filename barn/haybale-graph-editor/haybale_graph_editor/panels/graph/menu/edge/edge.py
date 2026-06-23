# barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/edge/edge.py
"""
Edge context-menu panels.

actions: EdgeContextActions, focus=EdgeFocus.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel
from haywire.ui.panel.layout import PanelLayout
from haywire.ui.panel.decorator import panel

from .....focuses import EdgeFocus
from .....state.edit_state import EditState
from .....editors.graph_canvas.handlers.context_menu_actions import EdgeContextActions
from ....properties.introspect.edge import (
    _state_from_context,
    _has_edge_errors,
    _has_edge_warnings,
    _render_edge_errors,
    _render_edge_warnings,
)

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


@panel(
    actions=EdgeContextActions,
    focus=EdgeFocus,
    label="Connection Errors",
    icon=hui.icon.error,
    order=0,
)
class EdgeErrorsMenuPanel(BasePanel):
    """Edge errors panel for the context menu (right-click on edge)."""

    actions: EdgeContextActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return _has_edge_errors(_state_from_context(ctx))

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        state = _state_from_context(ctx)
        if state is None:
            return
        with layout.container:
            _render_edge_errors(state)


@panel(
    actions=EdgeContextActions,
    focus=EdgeFocus,
    label="Connection Warnings",
    icon=hui.icon.warning,
    order=5,
)
class EdgeWarningsMenuPanel(BasePanel):
    """Edge warnings panel for the context menu."""

    actions: EdgeContextActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return _has_edge_warnings(_state_from_context(ctx))

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        state = _state_from_context(ctx)
        if state is None:
            return
        with layout.container:
            _render_edge_warnings(state)


@panel(
    actions=EdgeContextActions,
    focus=EdgeFocus,
    label="Insert Reroute",
    icon=hui.icon.edge,
    order=20,
)
class InsertRerouteMenuPanel(BasePanel):
    """Split the active edge and insert a reroute node in between.

    Available for DATA and CONTROL edges only. CALLBACK edges are excluded
    because the flow assembly manager reads the subscription key from the
    reroute's outlet at wiring time — before any worker has run to forward
    it — so the listener flow never registers correctly.
    """

    actions: EdgeContextActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        node_factory = ctx.app.node_factory
        if node_factory is None or node_factory.get_reroute_node() is None:
            return False
        edge = ctx.data[EditState].active_edge
        if edge is None:
            return False
        return not edge.is_callback_edge()

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        edge = ctx.data[EditState].active_edge
        if edge is None:
            return
        edge_id = edge.edge_id

        with layout:
            hui.button(
                "Insert Reroute",
                icon=hui.icon.edge,
                on_click=lambda: self.actions.split_edge_with_reroute(edge_id),
            )


@panel(
    actions=EdgeContextActions,
    focus=EdgeFocus,
    label="Delete Connection",
    icon=hui.icon.delete,
    order=30,
)
class DeleteEdgeMenuPanel(BasePanel):
    actions: EdgeContextActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.data[EditState].active_edge is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        edge = ctx.data[EditState].active_edge
        if edge is None:
            return
        edge_id = edge.edge_id

        with layout:
            hui.button(
                "Delete Connection",
                icon=hui.icon.delete,
                on_click=lambda: self.actions.delete_edge(edge_id),
            )


@panel(
    actions=EdgeContextActions,
    focus=EdgeFocus,
    label="Reconnect Edge",
    icon=hui.icon.edge,
    order=10,
)
class ReconnectEdgeMenuPanel(BasePanel):
    """Removes the edge and starts a new connection drag from the anchor pin.

    The provider's reconnect_active_edge action reads the active edge
    and the gesture state (which end was right-clicked) from its own
    _OpenMenuContext. The panel just invokes the verb.
    """

    actions: EdgeContextActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.data[EditState].active_edge is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        with layout:
            hui.button(
                "Reconnect",
                icon=hui.icon.edge,
                on_click=self.actions.reconnect_active_edge,
            )
