# haybale_studio/panels/properties/setting/execution.py
"""Execution settings panels, on the ``ExecutionInspectorSurface`` surface.

ExecutionSettingsPanel — auto-execute, timeouts, parallelism, caching, error handling

Log levels moved to ``DebugSurface`` — see debug.py.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.api.workbench import (
    BasePanel,
    ExecutionInspectorSurface,
    PanelLayout,
    hui,
    panel,
    render_schema,
)

if TYPE_CHECKING:
    from haywire.api.workbench import SessionContext


@panel(
    surface=ExecutionInspectorSurface,
    label="Execution",
    description="Auto-execute, timeouts, parallelism, caching and error handling.",
    icon=hui.icon.execution,
    order=10,
    default_open=True,
)
class ExecutionSettingsPanel(BasePanel):
    """Auto-execute, timeouts, parallelism, caching and error handling."""

    def draw(
        self,
        ctx: SessionContext,
        layout: PanelLayout,
    ) -> None:
        from haywire.core.execution.settings import ExecutionSettings

        registry = ctx.app.library_service.get_settings_registry()
        render_schema(ctx, ExecutionSettings, registry)
