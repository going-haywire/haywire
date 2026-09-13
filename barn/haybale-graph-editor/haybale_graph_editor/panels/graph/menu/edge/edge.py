# barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/edge/edge.py
"""
Edge context-menu panels — the surface ``EdgeMenu``.

``EdgeMenu`` is the menu half of the old ``EdgeFocus``, split out so the Edge
properties tab (``EdgeInspector``, which keeps ``id="edge"``) and this menu
stop being able to show each other's panels.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import ui

from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel
from haywire.ui.panel.layout import PanelLayout
from haywire.ui.panel.decorator import panel

from .....surfaces import EdgeActions, EdgeEditMenu, EdgeMenu
from .....state.edit_state import EditState
from ..component_rows import component_row
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
    surface=EdgeMenu,
    label="Connection Errors",
    icon=hui.icon.error,
    order=0,
)
class EdgeErrorsMenuPanel(BasePanel):
    """Edge errors panel for the context menu (right-click on edge)."""

    actions: EdgeActions

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
    surface=EdgeMenu,
    label="Connection Warnings",
    icon=hui.icon.warning,
    order=5,
)
class EdgeWarningsMenuPanel(BasePanel):
    """Edge warnings panel for the context menu."""

    actions: EdgeActions

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
    surface=EdgeMenu,
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

    actions: EdgeActions

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
            hui.menu_row(
                "Insert Reroute",
                icon=hui.icon.edge,
                on_click=lambda: self.actions.split_edge_with_reroute(edge_id),
            )


@panel(
    surface=EdgeMenu,
    hosts=(EdgeEditMenu,),
    label="Edit",
    icon=hui.icon.adapter,
    order=25,
)
class EditEdgeMenuPanel(BasePanel):
    """The "Edit…" row — a submenu over the adapters behind this edge.

    A hosting panel: it draws only the row and the flyout, piping the
    ``EdgeActions`` host one hop further, exactly as
    ``EditSelectionMenuPanel`` does for a node's Skin/Theme submenu. Mirrors
    that UX for the edge's adapter chain instead.
    """

    actions: EdgeActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        edge = ctx.data[EditState].active_edge
        return edge is not None and bool(edge.edge.chain_adapter_keys)

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        with layout:
            with hui.submenu_row("Edit", icon=hui.icon.adapter):
                self.render_surface(EdgeEditMenu, ctx)

    def draw_disabled(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        if ctx.data[EditState].active_edge is not None:
            with layout:
                hui.menu_row("Edit", icon=hui.icon.adapter, enabled=False)


@panel(
    surface=EdgeEditMenu,
    label="Adapters",
    icon=hui.icon.adapter,
    order=10,
)
class EdgeAdapterEditMenuPanel(BasePanel):
    """One row per adapter in the edge's chain, each opening its source.

    Reads ``Edge.chain_adapter_keys`` — the same ordered list the "Adapter
    Chain" properties panel displays — rather than walking
    ``first_adapter._chain`` itself.
    """

    actions: EdgeActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        edge = ctx.data[EditState].active_edge
        return edge is not None and bool(edge.edge.chain_adapter_keys)

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        from haywire.core.di.context import get_adapter_factory

        edge = ctx.data[EditState].active_edge
        if edge is None:
            return
        registry = get_adapter_factory().adapter_registry

        with layout:
            for key in edge.edge.chain_adapter_keys:
                adapter_cls = registry.get(key)
                label = adapter_cls.class_identity.label if adapter_cls is not None else key
                component_row(ctx, label, key, hui.icon.adapter)


@panel(
    surface=EdgeMenu,
    label="Propagation",
    description="Lazy propagation pulls data on demand instead of pushing it to the target node.",
    icon=hui.icon.edge_lazy,
    order=0,
)
class LazyEdgeMenuPanel(BasePanel):
    """Flip an edge between eager (push) and lazy (pull-on-demand) propagation.

    **The row rewrites itself on click rather than closing over its state**,
    for the same reason as ``CollapseSelectionMenuPanel``: ``hui.menu_row``
    does not dismiss its popup, so a handler that captured ``lazy`` at draw
    time would keep re-sending that value and the toggle would work exactly
    once. The current state is asked for on every click
    (``toggle_edge_lazy`` decides and returns the new state).

    The icon and label both name the current MODE, unlike Collapse's
    verb-labelled row: propagation is a standing property of the edge, not a
    one-shot action, so the row reads "Propagation: Lazy/Eager" rather than a
    command.
    """

    actions: EdgeActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.data[EditState].active_edge is not None

    @staticmethod
    def _row_text(lazy: bool) -> str:
        return f"Propagation: {'Lazy' if lazy else 'Eager'}"

    @staticmethod
    def _row_icon(lazy: bool) -> str:
        return hui.icon.edge_lazy if lazy else hui.icon.edge_eager

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        edge = ctx.data[EditState].active_edge
        if edge is None:
            return
        edge_id = edge.edge_id
        lazy = self.actions.edge_is_lazy(edge_id)

        with layout:
            row = hui.menu_row(
                self._row_text(lazy),
                icon=self._row_icon(lazy),
                tooltip="Lazy propagation pulls data on demand instead of pushing it on write.",
            )

        icon_el = next((c for c in row.default_slot.children if isinstance(c, ui.icon)), None)
        label_el = next((c for c in row.default_slot.children if isinstance(c, ui.label)), None)

        def _toggle() -> None:
            now_lazy = self.actions.toggle_edge_lazy(edge_id)
            if label_el is not None:
                label_el.set_text(self._row_text(now_lazy))
            if icon_el is not None:
                icon_el.set_name(self._row_icon(now_lazy))

        row.on("click", lambda _e=None: _toggle())


@panel(
    surface=EdgeMenu,
    label="Delete Connection",
    icon=hui.icon.delete,
    order=30,
)
class DeleteEdgeMenuPanel(BasePanel):
    actions: EdgeActions

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
            hui.menu_row(
                "Delete Connection",
                icon=hui.icon.delete,
                on_click=lambda: self.actions.delete_edge(edge_id),
            )


@panel(
    surface=EdgeMenu,
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

    actions: EdgeActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.data[EditState].active_edge is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        with layout:
            hui.menu_row(
                "Reconnect",
                icon=hui.icon.edge,
                on_click=self.actions.reconnect_active_edge,
            )
