# haybale_studio/panels/settings_canvas_panels.py
"""
Canvas-scope settings panels (CanvasFocus).

CanvasSettingsPanel   — grid, zoom, pan behaviour
NodeUISettingsPanel   — node dimensions, typography, label visibility
EdgeUISettingsPanel   — edge routing, width, animation
MinimapSettingsPanel  — minimap position and visibility
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.ui import elements as hui
from haywire.ui.components.zoom.settings import EditorPanZoomSettings
from haywire.ui.panel import BasePanel, PanelLayout
from haywire.ui.panel.decorator import panel
from haywire.ui.panel.render_utils import render_schema
from haywire.ui.components.minimap.settings import MinimapSettings
from haywire.ui.prefs.canvas import CanvasSettings
from haywire.ui.prefs.edge_ui import EdgeUISettings
from haywire.ui.panel.focus import CanvasFocus

from ..settings.node_skin_settings import NodeSkinSettings

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext

@panel(
    focus=CanvasFocus,
    label="Canvas",
    icon=hui.icon.canvas,
    order=10,
    default_open=True,
)
class CanvasSettingsPanel(BasePanel):
    """Grid, zoom, pan and background pattern."""

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        registry = ctx.app.library_service.get_settings_registry()
        render_schema(CanvasSettings, registry)


@panel(
    focus=CanvasFocus,
    label="Skins",
    description="Skin Configuration:Node dimensions, typography and label visibility.",
    icon=hui.icon.skin,
    order=20,
    default_open=False,
)
class NodeSkinSettingsPanel(BasePanel):
    """Node dimensions, typography and label visibility."""

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        registry = ctx.app.library_service.get_settings_registry()
        render_schema(NodeSkinSettings, registry)


@panel(
    focus=CanvasFocus,
    label="Edges",
    icon=hui.icon.edge,
    order=30,
    default_open=False,
)
class EdgeUISettingsPanel(BasePanel):
    """Edge routing, width and animation behaviour."""

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        registry = ctx.app.library_service.get_settings_registry()
        render_schema(EdgeUISettings, registry)


@panel(
    focus=CanvasFocus,
    label="Zoom & Pan",
    icon=hui.icon.canvas_zoom_pan,
    order=40,
    default_open=False,
)
class EditorZoomPanSettingsPanel(BasePanel):
    """Canvas pan/zoom behaviour settings."""

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        registry = ctx.app.library_service.get_settings_registry()
        render_schema(EditorPanZoomSettings, registry)


@panel(
    focus=CanvasFocus,
    label="Minimap",
    icon=hui.icon.canvas_minimap,
    order=40,
    default_open=False,
)
class MinimapSettingsPanel(BasePanel):
    """Minimap visibility, position and size."""

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        registry = ctx.app.library_service.get_settings_registry()
        render_schema(MinimapSettings, registry)
