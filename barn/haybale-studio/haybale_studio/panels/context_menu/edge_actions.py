"""
Context menu panels for edge actions.

Phase 1.5: action=EdgeContextActions, focus=EdgeFocus.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haybale_studio.focuses import EdgeFocus
from haywire.ui import elements as hui
from haywire.ui.graph_canvas.handlers.context_menu_actions import EdgeContextActions
from haywire.ui.panel import Panel
from haywire.ui.panel.layout import PanelLayout
from haywire.ui.panel.decorator import panel

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext


@panel(
    action=EdgeContextActions,
    focus=EdgeFocus,
    label="Reconnect Edge",
    icon=hui.icon.edge,
    order=10,
)
class ReconnectEdgePanel(Panel):
    """Removes the edge and starts a new connection drag from the anchor pin.

    The provider's reconnect_active_edge action reads the active edge
    and the gesture state (which end was right-clicked) from its own
    _OpenMenuContext. The panel just invokes the verb.
    """

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.active_edge.value is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: EdgeContextActions,
    ) -> None:
        layout.button(
            "Reconnect",
            icon=hui.icon.edge,
            on_click=actions.reconnect_active_edge,
        )
