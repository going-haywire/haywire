# haywire/ui/prefs/canvas.py
"""Canvas grid, zoom, and pan preference singleton."""

from haywire.core.reactive import Reactive, prop


class CanvasSettings(Reactive):
    """Global preferences controlling canvas grid, zoom, and pan behaviour."""

    # Background pattern (style, not color)
    bg_pattern: str = prop('dots', label='Background Pattern', description='Pattern style for canvas background', category='ui.canvas', order=10, choices=['none', 'dots', 'lines', 'cross'])

    # Grid
    grid_enabled:      bool = prop(True, label='Show Grid',         description='Display grid on canvas',          category='ui.canvas', order=20)
    grid_size:         int  = prop(20,   label='Grid Size',         description='Grid cell size in pixels',        category='ui.canvas', order=21, min=5,  max=100)
    grid_subdivisions: int  = prop(5,    label='Grid Subdivisions', description='Minor grid lines per major line', category='ui.canvas', order=22, min=1,  max=10)
    snap_to_grid:      bool = prop(True, label='Snap to Grid',      description='Snap nodes to grid when moving', category='ui.canvas', order=23)

    # Zoom
    zoom_min:       float = prop(0.1,  label='Minimum Zoom',   description='Minimum zoom level',                category='ui.canvas', order=30, min=0.05, max=0.5)
    zoom_max:       float = prop(4.0,  label='Maximum Zoom',   description='Maximum zoom level',                category='ui.canvas', order=31, min=1.0,  max=10.0)
    zoom_speed:     float = prop(0.1,  label='Zoom Speed',     description='Zoom sensitivity for scroll wheel', category='ui.canvas', order=32, min=0.01, max=0.5)
    zoom_to_cursor: bool  = prop(True, label='Zoom to Cursor', description='Zoom centred on cursor position',   category='ui.canvas', order=33)

    # Pan
    pan_speed:       float = prop(1.0,  label='Pan Speed',      description='Panning speed multiplier',                     category='ui.canvas', order=40, min=0.1, max=3.0)
    inertia_enabled: bool  = prop(True, label='Enable Inertia', description='Continue panning with momentum after release', category='ui.canvas', order=41)
