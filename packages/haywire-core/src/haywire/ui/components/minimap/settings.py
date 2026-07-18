# haywire/ui/prefs/minimap.py
"""Minimap layout and visibility preference singleton."""

from haywire.core.namespaces import NAMESPACE_UI_MINIMAP
from haywire.core.settings import setting
from haywire.core.settings.settings_framework import FrameworkSettings
from haywire.barn.builtin.types import BOOL, CHOICES, FLOAT, INT


class MinimapSettings(FrameworkSettings, namespace=NAMESPACE_UI_MINIMAP):
    """Global preferences controlling the minimap overlay layout and visibility."""

    enabled = setting[BOOL](True, label="Show Minimap", description="Display minimap overview")
    position = setting[CHOICES](
        "bottom-right",
        label="Minimap Position",
        description="Corner position of minimap",
        widget_config={"options": ["top-left", "top-right", "bottom-left", "bottom-right"]},
    )
    width = setting[INT](
        200,
        label="Minimap Width",
        description="Width of minimap in pixels",
        min=100,
        max=400,
    )
    opacity = setting[FLOAT](
        0.88,
        label="Active Opacity",
        description="Opacity when panning/zooming or hovering",
        category="opacities",
        min=0.1,
        max=1.0,
    )
    ghost_opacity = setting[FLOAT](
        0.15,
        label="Ghost Opacity",
        description="Resting opacity when idle",
        category="opacities",
        min=0.0,
        max=1.0,
    )
