# haywire/ui/pan_zoom/settings.py
"""Pan/zoom behaviour preference singleton."""

from haywire.core.namespaces import CATEGORY_EDITOR_PAN_ZOOM, NAMESPACE_EDITOR_PAN_ZOOM
from haywire.core.settings import field
from haywire.core.settings.schema import FrameworkSettings


class EditorPanZoomSettings(FrameworkSettings, namespace = NAMESPACE_EDITOR_PAN_ZOOM):
    """Global preferences controlling canvas pan/zoom behaviour."""

    zoom_sensitivity: float = field(
        1.0,
        label="Zoom Sensitivity",
        description="How fast scroll/pinch zooms the canvas",
        category=CATEGORY_EDITOR_PAN_ZOOM,
        order=10,
        min=0.01,
        max=2.0,
    )
    pan_sensitivity: float = field(
        1.0,
        label="Pan Sensitivity",
        description="How fast two-finger swipe pans the canvas",
        category=CATEGORY_EDITOR_PAN_ZOOM,
        order=20,
        min=0.1,
        max=5.0,
    )
    min_zoom: float = field(
        0.1,
        label="Minimum Zoom",
        description="Minimum zoom level",
        category=CATEGORY_EDITOR_PAN_ZOOM,
        order=30,
        min=0.01,
        max=0.5,
    )
    max_zoom: float = field(
        1.0,
        label="Maximum Zoom",
        description="Maximum zoom level",
        category=CATEGORY_EDITOR_PAN_ZOOM,
        order=40,
        min=0.5,
        max=5.0,
    )
    zoom_to_cursor: bool = field(
        True,
        label="Zoom to Cursor",
        description="Zoom centred on cursor position",
        category=CATEGORY_EDITOR_PAN_ZOOM,
        order=33,
    )
    inertia_enabled: bool = field(
        True,
        label="Enable Inertia",
        description="Continue panning with momentum after release",
        category=CATEGORY_EDITOR_PAN_ZOOM,
        order=41,
    )