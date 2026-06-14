"""
Node error panels — dual-host (PropertiesEditor + context-menu).

Two explicit per-host classes (matching the edge_panels pattern). Both render
identical content via a shared helper and gate on
ctx.data[EditState].active_node.state.get_errors() being non-empty.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel
from haywire.ui.panel.layout import PanelLayout
from haywire.ui.panel.decorator import panel

from ...focuses import NodeFocus, SelectionFocus
from ...state.edit_state import EditState
from ...editors.graph_canvas.handlers.context_menu_actions import NodeContextActions, SelectionContextActions

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


def _node_has_errors(ctx: "SessionContext") -> bool:
    node = ctx.data[EditState].active_node
    return node is not None and bool(node.state.get_errors())


def _render_node_errors(ctx: "SessionContext", layout: PanelLayout) -> None:
    from haywire.ui.errors.error_info import error_render_detail

    node = ctx.data[EditState].active_node
    if node is None:
        return
    errors = node.state.get_errors()
    if not errors:
        return
    with layout.container:
        for error in errors:
            error_render_detail(error)


@panel(
    focus=NodeFocus,
    label="Node Errors",
    icon=hui.icon.error,
    order=0,
)
class NodeErrorsPanel(BasePanel):
    """Node errors panel for PropertiesEditor."""

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return _node_has_errors(ctx)

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        _render_node_errors(ctx, layout)


@panel(
    actions=SelectionContextActions,
    focus=SelectionFocus,
    label="Node Errors",
    icon=hui.icon.error,
    order=0,
)
class ContextMenuNodeErrorsPanel(BasePanel):
    """Node errors panel for the unified selection context menu.

    Scoped to the primary (active) node's errors via _node_has_errors, which
    reads EditState.active_node — set by on_selection_context to the
    selection's primary. Display-only; calls no action verb.
    """

    actions: SelectionContextActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return _node_has_errors(ctx)

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        _render_node_errors(ctx, layout)
