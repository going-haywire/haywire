# haybale_studio/panels/properties/setting/canvas.py
"""Canvas & node appearance panels, on the ``CanvasSettingsSurface`` surface.

``CanvasSettings`` here is the settings bag one of these panels renders
(``haywire.ui.components.graph.settings``).

CanvasSettingsPanel          — grid, zoom, pan behaviour
EditorZoomPanSettingsPanel   — zoom/pan behaviour settings
MinimapSettingsPanel         — minimap position and visibility
EdgeDefaultSettingsPanel     — computed edges' arrow head, head size and width; edge hit padding
ArrangeSettingsPanel         — the gaps Arrange leaves between node cards

Debug HUD visibility moved to ``DebugSurface`` — see debug.py.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.api.workbench import BasePanel, CanvasSettingsSurface, PanelLayout, hui, panel, render_schema
from haywire.core.edge.settings import EdgeDefaultSettings
from haywire.core.graph.arrange_settings import ArrangeSettings
from haywire.ui.components.graph.settings import CanvasSettings
from haywire.ui.components.minimap.settings import MinimapSettings
from haywire.ui.components.zoom.settings import EditorPanZoomSettings

if TYPE_CHECKING:
    from haywire.api.workbench import SessionContext


@panel(
    surface=CanvasSettingsSurface,
    label="Grid",
    description="Grid, zoom, pan and background pattern.",
    icon=hui.icon.canvas_grid,
    order=10,
    default_open=False,
)
class CanvasSettingsPanel(BasePanel):
    """Grid, zoom, pan and background pattern."""

    def draw(
        self,
        ctx: SessionContext,
        layout: PanelLayout,
    ) -> None:
        registry = ctx.app.library_service.get_settings_registry()
        render_schema(ctx, CanvasSettings, registry)


@panel(
    surface=CanvasSettingsSurface,
    label="Zoom & Pan",
    description="Canvas pan/zoom behaviour settings.",
    icon=hui.icon.canvas_zoom_pan,
    order=40,
    default_open=False,
)
class EditorZoomPanSettingsPanel(BasePanel):
    """Canvas pan/zoom behaviour settings."""

    def draw(
        self,
        ctx: SessionContext,
        layout: PanelLayout,
    ) -> None:
        registry = ctx.app.library_service.get_settings_registry()
        render_schema(ctx, EditorPanZoomSettings, registry)


@panel(
    surface=CanvasSettingsSurface,
    label="Minimap",
    description="Minimap visibility, position and size.",
    icon=hui.icon.canvas_minimap,
    order=40,
    default_open=False,
)
class MinimapSettingsPanel(BasePanel):
    """Minimap visibility, position and size."""

    def draw(
        self,
        ctx: SessionContext,
        layout: PanelLayout,
    ) -> None:
        registry = ctx.app.library_service.get_settings_registry()
        render_schema(ctx, MinimapSettings, registry)


@panel(
    surface=CanvasSettingsSurface,
    label="Edges",
    description="Computed edges' arrow head, head size, width and hit padding.",
    icon=hui.icon.edge,
    order=30,
    default_open=False,
)
class EdgeDefaultSettingsPanel(BasePanel):
    """Computed edges' arrow head, head size and width (each graph may override them), and hit padding."""

    def draw(
        self,
        ctx: SessionContext,
        layout: PanelLayout,
    ) -> None:
        registry = ctx.app.library_service.get_settings_registry()
        render_schema(ctx, EdgeDefaultSettings, registry)


@panel(
    surface=CanvasSettingsSurface,
    label="Arrange",
    description="The gaps Arrange leaves between node cards.",
    icon=hui.icon.layout,
    order=50,
    default_open=False,
)
class ArrangeSettingsPanel(BasePanel):
    """The gaps Arrange leaves between node cards, for every graph."""

    def draw(
        self,
        ctx: SessionContext,
        layout: PanelLayout,
    ) -> None:
        registry = ctx.app.library_service.get_settings_registry()
        render_schema(ctx, ArrangeSettings, registry)
