# haywire/ui/components/pan_zoom/settings.py
"""Pan/zoom behaviour preference singleton."""

from haywire.core.namespaces import (
    CATEGORY_EDITOR_PAN_ZOOM,
    NAMESPACE_EDITOR_PAN_ZOOM,
    CATEGORY_EDITOR_HOVER,
)
from haywire.core.settings import setting
from haywire.core.settings.settings_framework import FrameworkSettings
from haywire.barn.builtin.types import BOOL, FLOAT, INT


class EditorPanZoomSettings(FrameworkSettings, namespace=NAMESPACE_EDITOR_PAN_ZOOM):
    """Global preferences controlling canvas pan/zoom behaviour."""

    zoom_sensitivity = setting[FLOAT](
        1.0,
        label="Zoom Sensitivity",
        description="How fast scroll/pinch zooms the canvas",
        category=CATEGORY_EDITOR_PAN_ZOOM,
        min=0.01,
        max=2.0,
    )
    pan_sensitivity = setting[FLOAT](
        1.0,
        label="Pan Sensitivity",
        description="How fast two-finger swipe pans the canvas",
        category=CATEGORY_EDITOR_PAN_ZOOM,
        min=0.1,
        max=5.0,
    )
    min_zoom = setting[FLOAT](
        0.0,
        label="Minimum Zoom",
        description=(
            "Lowest zoom level. 0 = automatic (zoom out until the canvas fills the "
            "viewport). A value above 0 overrides that, allowing further zoom-out."
        ),
        category=CATEGORY_EDITOR_PAN_ZOOM,
        min=0,
        max=1.0,
    )
    max_zoom = setting[FLOAT](
        1.0,
        label="Maximum Zoom",
        description="Maximum zoom level",
        category=CATEGORY_EDITOR_PAN_ZOOM,
        min=0.5,
        max=5.0,
    )

    # --- Hover magnifier -----------------------------------------------------
    # Readability aid: when zoomed out, dwelling on a node scales it up so its
    # content can be read without zooming in. Scaling fades to 1.0 (off) at/above
    # the cutoff zoom. Magnify only triggers after a dwell delay so passing the
    # cursor over a node on the way to another doesn't pop it; release on exit is
    # separately (usually quicker) timed.
    hover_scale_enabled = setting[BOOL](
        True,
        label="Hover Magnifier",
        description="Scale a node up on hover (when zoomed out) to read it without zooming in",
        category=CATEGORY_EDITOR_HOVER,
    )
    hover_scale_max = setting[FLOAT](
        1.5,
        label="Hover Magnify Amount",
        description="How much a node scales up on hover when fully zoomed out",
        category=CATEGORY_EDITOR_HOVER,
        min=1.0,
        max=5.0,
    )
    hover_scale_cutoff_zoom = setting[FLOAT](
        0.5,
        label="Hover Magnify Cutoff Zoom",
        description="At or above this zoom level the hover magnifier does nothing (scale 1.0)",
        category=CATEGORY_EDITOR_HOVER,
        min=0.1,
        max=1.0,
    )
    hover_enter_delay = setting[INT](
        350,
        label="Hover Magnify Delay (ms)",
        description="How long to dwell on a node before it magnifies",
        category=CATEGORY_EDITOR_HOVER,
        min=0,
        max=2000,
    )
    hover_exit_delay = setting[INT](
        0,
        label="Hover Magnify Release Delay (ms)",
        description="How long after leaving a node before it shrinks back",
        category=CATEGORY_EDITOR_HOVER,
        min=0,
        max=1000,
    )
