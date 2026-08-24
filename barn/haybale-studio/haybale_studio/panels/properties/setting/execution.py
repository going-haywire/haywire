# haybale_studio/panels/properties/setting/execution.py
"""
Execution settings panels, on the ``ExecutionInspector`` surface.

ExecutionSettingsPanel — auto-execute, timeouts, parallelism, caching, error handling
DebugSettingsPanel     — logging, execution visibility, visual debugging, data inspection
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel, PanelLayout
from haywire.ui.panel.decorator import panel
from haywire.ui.panel.render_utils import render_schema, render_keys
from haywire.core.namespaces import NAMESPACE_LIBRARY_LOG
from haywire.core.debug.debug_settings import DebugSettings

from haywire.barn.builtin.surfaces import ExecutionInspector

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


@panel(
    surface=ExecutionInspector,
    label="Execution",
    icon=hui.icon.execution,
    order=10,
    default_open=True,
)
class ExecutionSettingsPanel(BasePanel):
    """Auto-execute, timeouts, parallelism, caching and error handling."""

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        from haywire.core.execution.settings import ExecutionSettings

        registry = ctx.app.library_service.get_settings_registry()
        render_schema(ExecutionSettings, registry)


@panel(
    surface=ExecutionInspector,
    label="Log Levels",
    icon=hui.icon.debug,
    order=20,
    default_open=False,
)
class DebugSettingsPanel(BasePanel):
    """Logging, execution visibility, visual debugging and data inspection."""

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        registry = ctx.app.library_service.get_settings_registry()
        render_schema(DebugSettings, registry)
        render_keys(prefix=NAMESPACE_LIBRARY_LOG, registry=registry)
