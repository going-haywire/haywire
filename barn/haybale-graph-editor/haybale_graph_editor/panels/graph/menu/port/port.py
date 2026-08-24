# barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/port/port.py
"""
Pin context-menu panels — the surface ``PinMenu``.

Reached structurally now: the canvas detects a pin from ``data-pin-id``,
which ``render_pin`` emits on every pin from every skin, so every skin gains
this menu and none can suppress it. Both panels below are safe under that:
one is display-only, and the demote verb polls true only on a promoted inlet.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel
from haywire.ui.panel.layout import PanelLayout
from haywire.ui.panel.decorator import panel

from .....surfaces import PinMenu, PortActions
from .....state.edit_state import EditState


if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


@panel(
    surface=PinMenu,
    label="Port Info",
    icon=hui.icon.edge,
    order=10,
)
class PortInfoMenuPanel(BasePanel):
    actions: PortActions

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
    surface=PinMenu,
    label="Detach from setting",
    icon=hui.icon.delete,
    order=20,
)
class DetachSettingMenuPanel(BasePanel):
    """Shown only on a promoted inlet; demotes it back to a plain setting."""

    actions: PortActions

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
            hui.menu_row(
                "Detach from setting",
                icon=hui.icon.delete,
                on_click=lambda: self.actions.demote_setting(port.id),
            )
