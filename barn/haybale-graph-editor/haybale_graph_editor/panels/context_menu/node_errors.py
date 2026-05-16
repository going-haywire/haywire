"""
Node error panels — dual-host (PropertiesEditor + context-menu).

Phase 1.5: split into two explicit per-host classes (matches edge_panels
pattern). Both render identical content via a shared helper and gate on
ctx.data[EditState].active_node.state.get_errors() being non-empty.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel
from haywire.ui.panel.layout import PanelLayout
from haywire.ui.panel.decorator import panel

from ...focuses import NodeFocus
from ...state.edit_state import EditState
from ...editors.graph_canvas.handlers.context_menu_actions import NodeContextActions

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
    actions=NodeContextActions,
    focus=NodeFocus,
    label="Node Errors",
    icon=hui.icon.error,
    order=0,
)
class ContextMenuNodeErrorsPanel(BasePanel):
    """Node errors panel for the context menu (right-click on node)."""

    actions: NodeContextActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return _node_has_errors(ctx)

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        _render_node_errors(ctx, layout)
