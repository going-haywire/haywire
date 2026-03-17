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

from haybale_studio.panels._settings_panel_base import render_schema

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext


@panel(
    registry_id='settings_workbench',
    editor='properties',
    scope='app',
    label='Workbench',
    icon='palette',
    order=10,
    default_open=True,
)
class WorkbenchSettingsPanel(BasePanel):
    """Active workbench and node themes."""

    @classmethod
    def poll(cls, context: 'SessionContext') -> bool:
        return True

    def draw(self, context: 'SessionContext', layout: PanelLayout) -> None:
        from haybale_studio.settings.workbench import WorkbenchSettings, NodeThemeSettings
        registry = context.app.library_service.get_settings_registry()
        with layout.column():
            render_schema(WorkbenchSettings, registry)
            render_schema(NodeThemeSettings, registry)


@panel(
    registry_id='settings_editor',
    editor='properties',
    scope='app',
    label='Editor',
    icon='edit',
    order=20,
    default_open=False,
)
class EditorSettingsPanel(BasePanel):
    """Undo, auto-save, interaction, clipboard and node-creation behaviour."""

    @classmethod
    def poll(cls, context: 'SessionContext') -> bool:
        return True

    def draw(self, context: 'SessionContext', layout: PanelLayout) -> None:
        from haybale_studio.settings.editor import EditorSettings
        registry = context.app.library_service.get_settings_registry()
        with layout.column():
            render_schema(EditorSettings, registry)
