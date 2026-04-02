# haywire/ui/prefs/minimap.py
"""Minimap layout and visibility preference singleton."""

from haywire.core.namespaces import NAMESPACE_UI_MINIMAP
from haywire.core.settings import field
from haywire.core.settings.schema import FrameworkSettings


class MinimapSettings(FrameworkSettings, namespace = NAMESPACE_UI_MINIMAP):
    """Global preferences controlling the minimap overlay layout and visibility."""

    enabled: bool = field(
        True, 
        label="Show Minimap", 
        description="Display minimap overview", 
        order=10
    )
    position: str = field(
        "bottom-right",
        label="Minimap Position",
        description="Corner position of minimap",
        order=20,
        choices=["top-left", "top-right", "bottom-left", "bottom-right"],
    )
    width: int = field(
        200,
        label="Minimap Width",
        description="Width of minimap in pixels",
        order=30,
        min=100,
        max=400,
    )
    opacity: float = field(
        0.88,
        label="Active Opacity",
        description="Opacity when panning/zooming or hovering",
        category="opacities",
        order=40,
        min=0.1,
        max=1.0,
    )
    ghost_opacity: float = field(
        0.15,
        label="Ghost Opacity",
        description="Resting opacity when idle",
        category="opacities",
        order=50,
        min=0.0,
        max=1.0,
    )
    debug_info: bool = field(
        False,
        label="Show Debug Info",
        description="Overlay zoom/pan/scale values on the minimap",
        category="debug",
        order=60,
    )
