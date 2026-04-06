"""
Context menu panel for node runtime errors.

Contributed to editor='context_menu', scope='node.errors'.
Opened when the user right-clicks the error-count badge on a node.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from nicegui import ui

from haywire.ui import elements as hui
from haywire.ui.panel.base import BasePanel, PanelLayout
from haywire.ui.panel.decorator import panel

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext


@panel(
    editors="context_menu",
    scopes="node.errors",
    label="Node Errors",
    icon=hui.icon.error,
    order=10,
)
class NodeErrorsPanel(BasePanel):
    @classmethod
    def poll(cls, context: "SessionContext") -> bool:
        return (
            context.active_node is not None
            and bool(context.active_node.state.get_errors())
        )

    def draw(self, context: "SessionContext", layout: PanelLayout) -> None:
        from haywire.ui.errors.error_info import error_render_detail

        errors = context.active_node.state.get_errors()
        with layout._container:
            with ui.card().classes("p-2 max-w-md max-h-96 overflow-auto"):
                for idx, error in enumerate(errors):
                    with ui.expansion(
                        f"{idx + 1}. {error.operation or 'Error'}", icon=hui.icon.error
                    ).classes("w-full hw-text-danger"):
                        ui.label(error.message).classes("text-sm hw-text-danger mb-2")
                        error_render_detail(error)
