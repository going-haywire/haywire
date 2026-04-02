# haywire/ui/prefs/minimap.py
"""Minimap layout and visibility preference singleton."""

from haywire.core.settings import field
from haywire.core.settings.schema import FrameworkSettings


class MinimapSettings(FrameworkSettings, namespace="ui.minimap"):
    """Global preferences controlling the minimap overlay layout and visibility."""

    enabled: bool = field(
        True, label="Show Minimap", description="Display minimap overview", category="ui.minimap", order=10
    )
    position: str = field(
        "bottom-right",
        label="Minimap Position",
        description="Corner position of minimap",
        category="ui.minimap",
        order=11,
        choices=["top-left", "top-right", "bottom-left", "bottom-right"],
    )
    width: int = field(
        200,
        label="Minimap Width",
        description="Width of minimap in pixels",
        category="ui.minimap",
        order=12,
        min=100,
        max=400,
    )
    opacity: float = field(
        0.88,
        label="Opacity",
        description="Minimap transparency (0 = invisible, 1 = fully opaque)",
        category="ui.minimap",
        order=13,
        min=0.1,
        max=1.0,
    )
    debug_info: bool = field(
        False,
        label="Show Debug Info",
        description="Overlay zoom/pan/scale values on the minimap",
        category="ui.minimap",
        order=14,
    )
