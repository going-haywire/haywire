# haywire/ui/components/debug_overlay/settings.py
"""Graph-canvas debug/performance overlay preferences."""

from haywire.core.namespaces import NAMESPACE_UI_DEBUG_OVERLAY
from haywire.core.settings import setting
from haywire.core.settings.settings_framework import FrameworkSettings
from haywire.barn.builtin.types import BOOL, CHOICES


class DebugOverlaySettings(FrameworkSettings, namespace=NAMESPACE_UI_DEBUG_OVERLAY):
    """Global preferences controlling the canvas debug/performance overlay HUD."""

    enabled = setting[BOOL](
        False,
        label="Show Debug Overlay",
        description="Display the live performance/debug HUD on the canvas",
    )
    position = setting[CHOICES](
        "bottom-left",
        label="Overlay Position",
        description="Corner position of the debug overlay",
        widget_config={"options": ["top-left", "top-right", "bottom-left", "bottom-right"]},
    )
