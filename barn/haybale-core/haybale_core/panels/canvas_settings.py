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

from haywire.ui.components.zoom.settings import EditorPanZoomSettings
from haywire.ui.panel.decorator import panel
from haywire.ui.panel.base import BasePanel, PanelLayout
from haywire.ui.panel.render_utils import render_schema
from haywire.ui.components.minimap.settings import MinimapSettings
from haywire.ui.prefs.canvas import CanvasSettings
from haywire.ui.prefs.edge_ui import EdgeUISettings

from haybale_core.settings.node_skin_settings import NodeSkinSettings

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext

@panel(
    editors="properties",
    scopes="canvas",
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
        registry = context.app.library_service.get_settings_registry()
        render_schema(CanvasSettings, registry)

@panel(
    editors="properties",
    scopes="canvas",
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
        registry = context.app.library_service.get_settings_registry()
        render_schema(NodeSkinSettings, registry)

@panel(
    editors="properties",
    scopes="canvas",
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
        registry = context.app.library_service.get_settings_registry()
        render_schema(EdgeUISettings, registry)

@panel(
    editors="properties",
    scopes="canvas",
    label="Zoom & Pan",
    icon="edit",
    order=40,
    default_open=False,
)
class EditorZoomPanSettingsPanel(BasePanel):
    """Canvas pan/zoom behaviour settings."""

    @classmethod
    def poll(cls, context: "SessionContext") -> bool:
        return True

    def draw(self, context: "SessionContext", layout: PanelLayout) -> None:
        registry = context.app.library_service.get_settings_registry()
        render_schema(EditorPanZoomSettings, registry)


@panel(
    editors="properties",
    scopes="canvas",
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
        registry = context.app.library_service.get_settings_registry()
        render_schema(MinimapSettings, registry)
