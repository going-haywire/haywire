# haybale_studio/panels/debug_panel.py
"""
Debug-scope settings panel (scope='debug').

DebugSettingsPanel — logging, execution visibility, visual debugging, data inspection.
Per-library log level controls appear under "Debug / Library" via render_keys(),
populated dynamically as libraries are enabled/disabled.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.ui.panel.decorator import panel
from haywire.ui.panel.base import BasePanel, PanelLayout

from haybale_core.panels._settings_panel_base import render_schema, render_keys
from haywire.core.debug.keys import LIBRARY_LOG_PREFIX

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext


@panel(
    registry_id="settings_debug",
    editor="properties",
    scope="debug",
    label="Log Levels",
    icon="bug_report",
    order=10,
    default_open=False,
)
class DebugSettingsPanel(BasePanel):
    """Logging, execution visibility, visual debugging and data inspection."""

    @classmethod
    def poll(cls, context: "SessionContext") -> bool:
        return True

    def draw(self, context: "SessionContext", layout: PanelLayout) -> None:
        from haywire.core.debug.debug_settings import DebugSettings

        registry = context.app.library_service.get_settings_registry()
        render_schema(DebugSettings, registry)
        render_keys(prefix=LIBRARY_LOG_PREFIX, registry=registry)
