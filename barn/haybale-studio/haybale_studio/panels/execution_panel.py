# haybale_studio/panels/settings_execution_panel.py
"""
Execution-scope settings panel (ExecutionFocus).

ExecutionSettingsPanel — auto-execute, timeouts, parallelism, caching, error handling
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.ui import elements as hui
from haywire.ui.panel import Panel, PanelLayout
from haywire.ui.panel.decorator import panel
from haywire.ui.panel.render_utils import render_schema

from haybale_studio.editors.properties_editor_actions import PropertiesEditorActions
from haybale_studio.panels.focuses import ExecutionFocus

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext


@panel(
    action=PropertiesEditorActions,
    focus=ExecutionFocus,
    label="Execution",
    icon=hui.icon.execution,
    order=10,
    default_open=True,
)
class ExecutionSettingsPanel(Panel):
    """Auto-execute, timeouts, parallelism, caching and error handling."""

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: PropertiesEditorActions,
    ) -> None:
        from haywire.core.execution.settings import ExecutionSettings

        registry = ctx.app.library_service.get_settings_registry()
        render_schema(ExecutionSettings, registry)
