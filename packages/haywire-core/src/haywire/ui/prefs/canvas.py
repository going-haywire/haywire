# haywire/ui/prefs/canvas.py
"""Canvas grid, zoom, and pan preference singleton."""

from haywire.core.settings import setting
from haywire.core.settings.schema import FrameworkSettings

# TODO: Setup Canvas Settings


class CanvasSettings(FrameworkSettings, namespace="ui.canvas"):
    """Global preferences controlling canvas grid, zoom, and pan behaviour."""

    # Background pattern (style, not color)
    bg_pattern = setting[str](
        "dots",
        label="Background Pattern",
        description="Pattern style for canvas background",
        category="ui.canvas",
        order=10,
        choices=["none", "dots", "lines", "cross"],
    )

    # Grid
    grid_enabled = setting[bool](
        True, label="Show Grid", description="Display grid on canvas", category="ui.canvas", order=20
    )
    grid_size = setting[int](
        20,
        label="Grid Size",
        description="Grid cell size in pixels",
        category="ui.canvas",
        order=21,
        min=5,
        max=100,
    )
    grid_subdivisions = setting[int](
        5,
        label="Grid Subdivisions",
        description="Minor grid lines per major line",
        category="ui.canvas",
        order=22,
        min=1,
        max=10,
    )
    snap_to_grid = setting[bool](
        True,
        label="Snap to Grid",
        description="Snap nodes to grid when moving",
        category="ui.canvas",
        order=23,
    )
