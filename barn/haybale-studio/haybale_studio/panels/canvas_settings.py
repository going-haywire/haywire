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
from haywire.ui.panel import Panel, PanelLayout
from haywire.ui.panel.decorator import panel
from haywire.ui.panel.render_utils import render_schema
from haywire.ui.components.minimap.settings import MinimapSettings
from haywire.ui.prefs.canvas import CanvasSettings
from haywire.ui.prefs.edge_ui import EdgeUISettings

from haybale_core.settings.node_skin_settings import NodeSkinSettings
from haybale_studio.editors.properties_editor_actions import PropertiesEditorActions
from haybale_studio.panels.focuses import CanvasFocus

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext


@panel(
    action=PropertiesEditorActions,
    focus=CanvasFocus,
    label="Canvas",
    icon=hui.icon.canvas,
    order=10,
    default_open=True,
)
class CanvasSettingsPanel(Panel):
    """Grid, zoom, pan and background pattern."""

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: PropertiesEditorActions,
    ) -> None:
        registry = ctx.app.library_service.get_settings_registry()
        render_schema(CanvasSettings, registry)


@panel(
    action=PropertiesEditorActions,
    focus=CanvasFocus,
    label="Skins",
    description="Skin Configuration:Node dimensions, typography and label visibility.",
    icon=hui.icon.skin,
    order=20,
    default_open=False,
)
class NodeSkinSettingsPanel(Panel):
    """Node dimensions, typography and label visibility."""

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: PropertiesEditorActions,
    ) -> None:
        registry = ctx.app.library_service.get_settings_registry()
        render_schema(NodeSkinSettings, registry)


@panel(
    action=PropertiesEditorActions,
    focus=CanvasFocus,
    label="Edges",
    icon=hui.icon.edge,
    order=30,
    default_open=False,
)
class EdgeUISettingsPanel(Panel):
    """Edge routing, width and animation behaviour."""

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: PropertiesEditorActions,
    ) -> None:
        registry = ctx.app.library_service.get_settings_registry()
        render_schema(EdgeUISettings, registry)


@panel(
    action=PropertiesEditorActions,
    focus=CanvasFocus,
    label="Zoom & Pan",
    icon=hui.icon.canvas_zoom_pan,
    order=40,
    default_open=False,
)
class EditorZoomPanSettingsPanel(Panel):
    """Canvas pan/zoom behaviour settings."""

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: PropertiesEditorActions,
    ) -> None:
        registry = ctx.app.library_service.get_settings_registry()
        render_schema(EditorPanZoomSettings, registry)


@panel(
    action=PropertiesEditorActions,
    focus=CanvasFocus,
    label="Minimap",
    icon=hui.icon.canvas_minimap,
    order=40,
    default_open=False,
)
class MinimapSettingsPanel(Panel):
    """Minimap visibility, position and size."""

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: PropertiesEditorActions,
    ) -> None:
        registry = ctx.app.library_service.get_settings_registry()
        render_schema(MinimapSettings, registry)
