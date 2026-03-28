# haybale_studio/panels/settings_execution_panel.py
"""
Execution-scope settings panel (scope='execution').

ExecutionSettingsPanel — auto-execute, timeouts, parallelism, caching, error handling
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.ui.panel.decorator import panel
from haywire.ui.panel.base import BasePanel, PanelLayout

from haybale_core.panels._settings_panel_base import render_schema

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext


@panel(
    registry_id="settings_execution",
    editor="properties",
    scope="execution",
    label="Execution",
    icon="play_circle",
    order=10,
    default_open=True,
)
class ExecutionSettingsPanel(BasePanel):
    """Auto-execute, timeouts, parallelism, caching and error handling."""

    @classmethod
    def poll(cls, context: "SessionContext") -> bool:
        return True

    def draw(self, context: "SessionContext", layout: PanelLayout) -> None:
        from haybale_studio.settings.execution import ExecutionSettings

        registry = context.app.library_service.get_settings_registry()
        render_schema(ExecutionSettings, registry)
