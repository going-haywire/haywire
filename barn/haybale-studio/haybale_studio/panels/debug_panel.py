# haybale_studio/panels/debug_panel.py
"""
Debug-scope settings panel (ExecutionFocus).

DebugSettingsPanel — logging, execution visibility, visual debugging, data inspection.
Per-library log level controls appear under "Debug / Library" via render_keys(),
populated dynamically as libraries are enabled/disabled.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.ui import elements as hui
from haywire.ui.panel import Panel, PanelLayout
from haywire.ui.panel.decorator import panel
from haywire.ui.panel.render_utils import render_schema, render_keys
from haywire.core.namespaces import NAMESPACE_LIBRARY_LOG
from haywire.core.debug.debug_settings import DebugSettings

from haybale_studio.editors.properties_editor_actions import PropertiesEditorActions
from haybale_studio.focuses import ExecutionFocus

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext


@panel(
    action=PropertiesEditorActions,
    focus=ExecutionFocus,
    label="Log Levels",
    icon=hui.icon.debug,
    order=20,
    default_open=False,
)
class DebugSettingsPanel(Panel):
    """Logging, execution visibility, visual debugging and data inspection."""

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: PropertiesEditorActions,
    ) -> None:
        registry = ctx.app.library_service.get_settings_registry()
        render_schema(DebugSettings, registry)
        render_keys(prefix=NAMESPACE_LIBRARY_LOG, registry=registry)
