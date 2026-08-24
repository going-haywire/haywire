# haybale_studio/panels/properties/setting/debug.py
"""
Debug settings panels, on the ``DebugSurface`` surface.

DebugSettingsPanel        — log levels (global baseline, per-group, per-library)
DebugOverlaySettingsPanel — debug HUD visibility and position

Both were previously split across ``ExecutionInspector`` and
``CanvasSettings`` respectively; they share one surface now since neither is
really an execution or canvas concern.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel, PanelLayout
from haywire.ui.panel.decorator import panel
from haywire.ui.panel.render_utils import render_schema, render_keys
from haywire.core.namespaces import NAMESPACE_LIBRARY_LOG
from haywire.core.debug.debug_settings import DebugSettings
from haywire.ui.components.debug_overlay.settings import DebugOverlaySettings

from haywire.barn.builtin.surfaces import DebugSurface

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


@panel(
    surface=DebugSurface,
    label="Log Levels",
    icon=hui.icon.debug,
    order=10,
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


@panel(
    surface=DebugSurface,
    label="Debug Overlay",
    icon=hui.icon.debug,
    order=20,
    default_open=False,
)
class DebugOverlaySettingsPanel(BasePanel):
    """Performance/debug HUD visibility and position."""

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        registry = ctx.app.library_service.get_settings_registry()
        render_schema(DebugOverlaySettings, registry)
