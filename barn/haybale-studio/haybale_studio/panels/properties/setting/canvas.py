# haybale_studio/panels/properties/setting/canvas.py
"""
Canvas & node appearance panels, on the ``CanvasSettings`` surface.

Note the name collides twice over: the *surface* ``CanvasSettings``
(``haywire.barn.builtin.surfaces``) is imported here as ``CanvasSurface``,
because ``haywire.ui.components.graph.settings.CanvasSettings`` — the
settings *bag* one of these panels renders — already holds the plain name in
this module.

CanvasSettingsPanel          — grid, zoom, pan behaviour
EditorZoomPanSettingsPanel   — zoom/pan behaviour settings
MinimapSettingsPanel         — minimap position and visibility
EdgeDefaultSettingsPanel     — computed edges' arrow head, head size and width; edge hit padding
ArrangeSettingsPanel         — the gaps Arrange leaves between node cards

Debug HUD visibility moved to ``DebugSurface`` — see debug.py.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.core.edge.settings import EdgeDefaultSettings
from haywire.core.graph.arrange_settings import ArrangeSettings
from haywire.ui import elements as hui
from haywire.ui.components.zoom.settings import EditorPanZoomSettings
from haywire.ui.panel import BasePanel, PanelLayout
from haywire.ui.panel.decorator import panel
from haywire.ui.panel.render_utils import render_schema
from haywire.ui.components.minimap.settings import MinimapSettings
from haywire.ui.components.graph.settings import CanvasSettings
from haywire.barn.builtin.surfaces import CanvasSettings as CanvasSurface

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


@panel(
    surface=CanvasSurface,
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
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        registry = ctx.app.library_service.get_settings_registry()
        render_schema(ctx, CanvasSettings, registry)


@panel(
    surface=CanvasSurface,
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
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        registry = ctx.app.library_service.get_settings_registry()
        render_schema(ctx, EditorPanZoomSettings, registry)


@panel(
    surface=CanvasSurface,
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
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        registry = ctx.app.library_service.get_settings_registry()
        render_schema(ctx, MinimapSettings, registry)


@panel(
    surface=CanvasSurface,
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
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        registry = ctx.app.library_service.get_settings_registry()
        render_schema(ctx, EdgeDefaultSettings, registry)


@panel(
    surface=CanvasSurface,
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
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        registry = ctx.app.library_service.get_settings_registry()
        render_schema(ctx, ArrangeSettings, registry)
