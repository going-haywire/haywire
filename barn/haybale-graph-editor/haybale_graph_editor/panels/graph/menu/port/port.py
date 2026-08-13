# barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/port/port.py
"""
Port context-menu panels.

actions: PortContextActions (empty marker), focus=PinFocus.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel
from haywire.ui.panel.layout import PanelLayout
from haywire.ui.panel.decorator import panel

from .....focuses import PinFocus
from .....state.edit_state import EditState
from .....editors.graph_canvas.handlers.context_menu_actions import PortContextActions


if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


@panel(
    actions=PortContextActions,
    focus=PinFocus,
    label="Port Info",
    icon=hui.icon.edge,
    order=10,
)
class PortInfoMenuPanel(BasePanel):
    actions: PortContextActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.data[EditState].active_port is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        port = ctx.data[EditState].active_port
        if port is None:
            return
        with layout.container:
            hui.section_label(port.id)
            if port.description:
                hui.label(port.description)
            hui.info_label(f"Flow: {port.flow_type.value}")
            type_key = port.stored_type.class_identity.registry_key
            hui.info_label(f"Type: {type_key}")


@panel(
    actions=PortContextActions,
    focus=PinFocus,
    label="Detach from setting",
    icon=hui.icon.delete,
    order=20,
)
class DetachSettingMenuPanel(BasePanel):
    """Shown only on a promoted inlet; demotes it back to a plain setting."""

    actions: PortContextActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        port = ctx.data[EditState].active_port
        return port is not None and port.promoted

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        port = ctx.data[EditState].active_port
        if port is None:
            return
        with layout:
            hui.button(
                "Detach from setting",
                icon=hui.icon.delete,
                on_click=lambda: self.actions.demote_setting(port.id),
            )
