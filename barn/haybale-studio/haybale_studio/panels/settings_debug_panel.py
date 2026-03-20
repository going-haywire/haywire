# haybale_studio/panels/settings_debug_panel.py
"""
Debug-scope settings panel (scope='debug').

DebugSettingsPanel — logging, execution visibility, visual debugging, data inspection
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.ui.panel.decorator import panel
from haywire.ui.panel.base import BasePanel, PanelLayout

from haybale_studio.panels._settings_panel_base import render_schema

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext


@panel(
    registry_id='settings_debug',
    editor='properties',
    scope='debug',
    label='Debug',
    icon='bug_report',
    order=10,
    default_open=True,
)
class DebugSettingsPanel(BasePanel):
    """Logging, execution visibility, visual debugging and data inspection."""

    @classmethod
    def poll(cls, context: 'SessionContext') -> bool:
        return True

    def draw(self, context: 'SessionContext', layout: PanelLayout) -> None:
        from haybale_studio.settings.debug import DebugSettings
        registry = context.app.library_service.get_settings_registry()
        render_schema(DebugSettings, registry)
