# haybale_studio/panels/settings_app_panels.py
"""
Application-scope settings panels (scope='app').

WorkbenchSettingsPanel  — active workbench theme
EditorSettingsPanel     — undo, auto-save, interaction, clipboard, node creation
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.ui.panel.decorator import panel
from haywire.ui.panel.base import BasePanel, PanelLayout
from haywire.ui.panel.render_utils import render_schema

from haywire.ui.components.zoom.settings import EditorPanZoomSettings
from haybale_studio.settings.theme_settings import WorkbenchThemeSettings, NodeThemeSettings
from haywire.ui.skin.settings import NodeDefaultSkinSettings
from haywire.ui.prefs.editor import EditorSettings

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext


@panel(
    editors="properties",
    scopes="app",
    label="Workbench",
    icon="palette",
    order=10,
    default_open=True,
)
class ThemeSettingsPanel(BasePanel):
    """Active workbench and node themes."""

    @classmethod
    def poll(cls, context: "SessionContext") -> bool:
        return True

    def draw(self, context: "SessionContext", layout: PanelLayout) -> None:
        registry = context.app.library_service.get_settings_registry()
        render_schema(WorkbenchThemeSettings, registry)
        render_schema(NodeThemeSettings, registry)

@panel(
    editors="properties",
    scopes="app",
    label="Default Skins",
    icon="palette",
    order=20,
    default_open=False,
)
class NodeSkinDefaultPanel(BasePanel):
    """Node Default Skins."""

    @classmethod
    def poll(cls, context: "SessionContext") -> bool:
        return True

    def draw(self, context: "SessionContext", layout: PanelLayout) -> None:
        registry = context.app.library_service.get_settings_registry()
        render_schema(NodeDefaultSkinSettings, registry)


@panel(
    editors="properties",
    scopes="app",
    label="Editor",
    icon="edit",
    order=30,
    default_open=False,
)
class EditorSettingsPanel(BasePanel):
    """Undo, auto-save, interaction, clipboard and node-creation behaviour."""

    @classmethod
    def poll(cls, context: "SessionContext") -> bool:
        return True

    def draw(self, context: "SessionContext", layout: PanelLayout) -> None:
        registry = context.app.library_service.get_settings_registry()
        render_schema(EditorSettings, registry)

