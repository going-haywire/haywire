# haybale_studio/panels/properties/setting/debug.py
"""Debug settings panels, on the ``DebugSurface`` surface.

DebugSettingsPanel        — log levels (global baseline, per-group, per-library)
DebugOverlaySettingsPanel — debug HUD visibility and position

Both were previously split across ``ExecutionInspectorSurface`` and
``CanvasSettingsSurface`` respectively; they share one surface now since neither is
really an execution or canvas concern.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.api.workbench import BasePanel, DebugSurface, PanelLayout, hui, panel, render_schema
from haywire.core.debug.debug_settings import DebugSettings
from haywire.core.namespaces import NAMESPACE_LIBRARY_LOG
from haywire.ui.components.debug_overlay.settings import DebugOverlaySettings
from haywire.ui.panel.render_utils import render_keys

if TYPE_CHECKING:
    from haywire.api.workbench import SessionContext


@panel(
    surface=DebugSurface,
    label="Log Levels",
    description="Logging, execution visibility, visual debugging and data inspection.",
    icon=hui.icon.debug,
    order=10,
    default_open=False,
)
class DebugSettingsPanel(BasePanel):
    """Logging, execution visibility, visual debugging and data inspection."""

    def draw(
        self,
        ctx: SessionContext,
        layout: PanelLayout,
    ) -> None:
        registry = ctx.app.library_service.get_settings_registry()
        render_schema(ctx, DebugSettings, registry)
        render_keys(ctx, prefix=NAMESPACE_LIBRARY_LOG, registry=registry)


@panel(
    surface=DebugSurface,
    label="Debug Overlay",
    description="Performance/debug HUD visibility and position.",
    icon=hui.icon.debug,
    order=20,
    default_open=False,
)
class DebugOverlaySettingsPanel(BasePanel):
    """Performance/debug HUD visibility and position."""

    def draw(
        self,
        ctx: SessionContext,
        layout: PanelLayout,
    ) -> None:
        registry = ctx.app.library_service.get_settings_registry()
        render_schema(ctx, DebugOverlaySettings, registry)
