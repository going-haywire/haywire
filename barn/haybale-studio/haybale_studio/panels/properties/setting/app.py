# haybale_studio/panels/properties/setting/app.py
"""
Application-scope settings panels (AppFocus).

ThemeSettingsPanel    — active workbench theme
NodeSkinDefaultPanel  — default node skin settings
EditorSettingsPanel   — undo, auto-save, interaction, clipboard, node creation
FarmhandSettingsPanel — Farmhand MCP server enable/auth, studio port/loopback
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel, PanelLayout
from haywire.ui.panel.decorator import panel
from haywire.ui.panel.render_utils import render_schema

from haybale_studio.settings.theme_settings import WorkbenchThemeSettings, NodeThemeSettings
from haywire.core.skin.settings import NodeDefaultSkinSettings
from haywire.ui.prefs.editor import EditorSettings

from haywire.barn.builtin.focuses import AppFocus

from haywire_studio.farmhand.settings import FarmhandSettings
from haywire_studio.network.settings import NetworkSettings

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


@panel(
    focus=AppFocus,
    label="Workbench",
    icon=hui.icon.theme,
    order=10,
    default_open=True,
)
class ThemeSettingsPanel(BasePanel):
    """Active workbench and node themes."""

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        registry = ctx.app.library_service.get_settings_registry()
        render_schema(WorkbenchThemeSettings, registry)
        render_schema(NodeThemeSettings, registry)


@panel(
    focus=AppFocus,
    label="Default Skins",
    icon=hui.icon.skin,
    order=20,
    default_open=False,
)
class NodeSkinDefaultPanel(BasePanel):
    """Node Default Skins."""

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        registry = ctx.app.library_service.get_settings_registry()
        render_schema(NodeDefaultSkinSettings, registry)


@panel(
    focus=AppFocus,
    label="Editor",
    icon=hui.icon.edit,
    order=30,
    default_open=False,
)
class EditorSettingsPanel(BasePanel):
    """Undo, auto-save, interaction, clipboard and node-creation behaviour."""

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        registry = ctx.app.library_service.get_settings_registry()
        render_schema(EditorSettings, registry)


@panel(
    focus=AppFocus,
    label="Network",
    icon=hui.icon.network,
    order=40,
    default_open=False,
)
class NetworkSettingsPanel(BasePanel):
    """Network settings for the studio."""

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        registry = ctx.app.library_service.get_settings_registry()
        render_schema(NetworkSettings, registry)
        render_schema(FarmhandSettings, registry)
