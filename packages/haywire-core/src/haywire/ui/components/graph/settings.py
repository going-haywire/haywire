# haywire/ui/components/graph/canvas.py
"""Canvas grid, zoom, and pan preference singleton."""

from haywire.core.settings import setting
from haywire.core.settings.settings_framework import FrameworkSettings
from haywire.barn.builtin.types import BOOL, CHOICES, COLOR, INT


class CanvasSettings(FrameworkSettings, namespace="ui.canvas"):
    """Global preferences controlling canvas grid, zoom, and pan behaviour."""

    # Background pattern (style, not color)
    bg_pattern = setting[CHOICES](
        "dots",
        label="Background Pattern",
        description="Pattern style for canvas background",
        category="ui.canvas",
        widget_config={"options": ["none", "dots", "lines", "cross"]},
    )
    grid_color = setting[COLOR](
        "#808080",
        label="Grid Color",
        description="Color of the canvas grid",
        category="ui.canvas",
    )

    # Grid
    grid_enabled = setting[BOOL](
        False, label="Show Grid", description="Display grid on canvas", category="ui.canvas"
    )
    grid_size = setting[INT](
        50,
        label="Grid Size",
        description="Grid cell size in pixels",
        category="ui.canvas",
        min=5,
        max=100,
    )
    grid_subdivisions = setting[INT](
        1,
        label="Grid Subdivisions",
        description="Minor grid lines per major line",
        category="ui.canvas",
        min=1,
        max=10,
    )
    snap_to_grid = setting[BOOL](
        False,
        label="Snap to Grid",
        description="Snap nodes to grid when moving",
        category="ui.canvas",
    )
    snap_scale_to_grid = setting[BOOL](
        False,
        label="Snap Scale to Grid",
        description="Snap the dragged edge to the grid when resizing a node",
        category="ui.canvas",
    )
