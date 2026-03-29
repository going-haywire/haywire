# haybale_studio/panels/settings_canvas_panels.py
"""
Canvas-scope settings panels (scope='canvas').

CanvasSettingsPanel   — grid, zoom, pan behaviour
NodeUISettingsPanel   — node dimensions, typography, label visibility
EdgeUISettingsPanel   — edge routing, width, animation
MinimapSettingsPanel  — minimap position and visibility
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.ui.panel.decorator import panel
from haywire.ui.panel.base import BasePanel, PanelLayout

from ._settings_panel_base import render_schema

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext


@panel(
    registry_id="settings_canvas",
    editor="properties",
    scope="canvas",
    label="Canvas",
    icon="grid_on",
    order=10,
    default_open=True,
)
class CanvasSettingsPanel(BasePanel):
    """Grid, zoom, pan and background pattern."""

    @classmethod
    def poll(cls, context: "SessionContext") -> bool:
        return True

    def draw(self, context: "SessionContext", layout: PanelLayout) -> None:
        from haywire.ui.prefs.canvas import CanvasSettings

        registry = context.app.library_service.get_settings_registry()
        render_schema(CanvasSettings, registry)

@panel(
    editor="properties",
    scope="canvas",
    label="Node Skins",
    description="Node dimensions, typography and label visibility.",
    icon="widgets",
    order=20,
    default_open=False,
)
class NodeSkinSettingsPanel(BasePanel):
    """Node dimensions, typography and label visibility."""

    @classmethod
    def poll(cls, context: "SessionContext") -> bool:
        return True

    def draw(self, context: "SessionContext", layout: PanelLayout) -> None:
        from haybale_core.settings.node_skin_settings import NodeSkinSettings

        registry = context.app.library_service.get_settings_registry()
        render_schema(NodeSkinSettings, registry)

@panel(
    registry_id="settings_edge_ui",
    editor="properties",
    scope="canvas",
    label="Edges",
    icon="cable",
    order=30,
    default_open=False,
)
class EdgeUISettingsPanel(BasePanel):
    """Edge routing, width and animation behaviour."""

    @classmethod
    def poll(cls, context: "SessionContext") -> bool:
        return True

    def draw(self, context: "SessionContext", layout: PanelLayout) -> None:
        from haywire.ui.prefs.edge_ui import EdgeUISettings

        registry = context.app.library_service.get_settings_registry()
        render_schema(EdgeUISettings, registry)


@panel(
    registry_id="settings_minimap",
    editor="properties",
    scope="canvas",
    label="Minimap",
    icon="map",
    order=40,
    default_open=False,
)
class MinimapSettingsPanel(BasePanel):
    """Minimap visibility, position and size."""

    @classmethod
    def poll(cls, context: "SessionContext") -> bool:
        return True

    def draw(self, context: "SessionContext", layout: PanelLayout) -> None:
        from haywire.ui.prefs.minimap import MinimapSettings

        registry = context.app.library_service.get_settings_registry()
        render_schema(MinimapSettings, registry)
