# haybale_studio/panels/debug_panel.py
"""
Debug-scope settings panel (scope='debug').

DebugSettingsPanel — logging, execution visibility, visual debugging, data inspection.
Per-library log level controls appear under "Debug / Library" via render_keys(),
populated dynamically as libraries are enabled/disabled.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.ui import elements as hui
from haywire.ui.panel.decorator import panel
from haywire.ui.panel.base import BasePanel, PanelLayout
from haywire.ui.panel.render_utils import render_schema, render_keys
from haywire.core.namespaces import NAMESPACE_LIBRARY_LOG
from haywire.core.debug.debug_settings import DebugSettings

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext


@panel(
    editors="properties",
    scopes="execution",  
    label="Log Levels",
    icon=hui.icon.debug,
    order=20,
    default_open=False,
)
class DebugSettingsPanel(BasePanel):
    """Logging, execution visibility, visual debugging and data inspection."""

    @classmethod
    def poll(cls, context: "SessionContext") -> bool:
        return True

    def draw(self, context: "SessionContext", layout: PanelLayout) -> None:
        registry = context.app.library_service.get_settings_registry()
        render_schema(DebugSettings, registry)
        render_keys(prefix=NAMESPACE_LIBRARY_LOG, registry=registry)
