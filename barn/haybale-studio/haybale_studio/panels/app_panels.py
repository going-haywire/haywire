# haybale_studio/panels/settings_app_panels.py
"""
Application-scope settings panels (AppFocus).

WorkbenchSettingsPanel  — active workbench theme
EditorSettingsPanel     — undo, auto-save, interaction, clipboard, node creation
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.ui import elements as hui
from haywire.ui.panel import Panel, PanelLayout
from haywire.ui.panel.decorator import panel
from haywire.ui.panel.render_utils import render_schema

from haybale_studio.settings.theme_settings import WorkbenchThemeSettings, NodeThemeSettings
from haywire.ui.skin.settings import NodeDefaultSkinSettings
from haywire.ui.prefs.editor import EditorSettings

from haybale_studio.editors.properties_editor_actions import PropertiesEditorActions
from haybale_studio.focuses import AppFocus

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext


@panel(
    action=PropertiesEditorActions,
    focus=AppFocus,
    label="Workbench",
    icon=hui.icon.theme,
    order=10,
    default_open=True,
)
class ThemeSettingsPanel(Panel):
    """Active workbench and node themes."""

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: PropertiesEditorActions,
    ) -> None:
        registry = ctx.app.library_service.get_settings_registry()
        render_schema(WorkbenchThemeSettings, registry)
        render_schema(NodeThemeSettings, registry)


@panel(
    action=PropertiesEditorActions,
    focus=AppFocus,
    label="Default Skins",
    icon=hui.icon.skin,
    order=20,
    default_open=False,
)
class NodeSkinDefaultPanel(Panel):
    """Node Default Skins."""

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: PropertiesEditorActions,
    ) -> None:
        registry = ctx.app.library_service.get_settings_registry()
        render_schema(NodeDefaultSkinSettings, registry)


@panel(
    action=PropertiesEditorActions,
    focus=AppFocus,
    label="Editor",
    icon=hui.icon.edit,
    order=30,
    default_open=False,
)
class EditorSettingsPanel(Panel):
    """Undo, auto-save, interaction, clipboard and node-creation behaviour."""

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: PropertiesEditorActions,
    ) -> None:
        registry = ctx.app.library_service.get_settings_registry()
        render_schema(EditorSettings, registry)
