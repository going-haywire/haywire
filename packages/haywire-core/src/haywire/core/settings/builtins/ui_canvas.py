# haywire/core/settings/builtins/ui_canvas.py
"""UI Canvas/graph background settings."""

from ..schema import GlobalSettings
from ..types import Color
from ..descriptors import setting


class CanvasUISettings(GlobalSettings, namespace='ui.canvas'):
    """Global settings controlling the graph canvas appearance and behaviour."""

    # Background
    bg_color:   Color = setting('#1e1e1e', label='Canvas Background',  description='Background color of the graph canvas', category='ui.canvas', order=10, widget='color')
    bg_pattern: str   = setting('dots',    label='Background Pattern', description='Pattern style for canvas background', category='ui.canvas', order=11, choices=['none', 'dots', 'lines', 'cross'])

    # Grid
    grid_enabled:     bool  = setting(True,     label='Show Grid',          description='Display grid on canvas',                   category='ui.canvas', order=20)
    grid_size:        int   = setting(20,        label='Grid Size',          description='Grid cell size in pixels',                 category='ui.canvas', order=21, min=5,  max=100)
    grid_color:       Color = setting('#2d2d2d', label='Grid Color',         description='Color of grid lines',                     category='ui.canvas', order=22, widget='color')
    grid_subdivisions: int  = setting(5,         label='Grid Subdivisions',  description='Number of minor grid lines per major line', category='ui.canvas', order=23, min=1, max=10)
    snap_to_grid:     bool  = setting(True,      label='Snap to Grid',       description='Snap nodes to grid when moving',           category='ui.canvas', order=24)

    # Zoom
    zoom_min:      float = setting(0.1, label='Minimum Zoom',   description='Minimum zoom level',                   category='ui.canvas', order=30, min=0.05, max=0.5)
    zoom_max:      float = setting(4.0, label='Maximum Zoom',   description='Maximum zoom level',                   category='ui.canvas', order=31, min=1.0,  max=10.0)
    zoom_speed:    float = setting(0.1, label='Zoom Speed',     description='Zoom sensitivity for scroll wheel',    category='ui.canvas', order=32, min=0.01, max=0.5)
    zoom_to_cursor: bool = setting(True, label='Zoom to Cursor', description='Zoom centered on cursor position',   category='ui.canvas', order=33)

    # Pan
    pan_speed:       float = setting(1.0,  label='Pan Speed',      description='Panning speed multiplier',                       category='ui.canvas', order=40, min=0.1, max=3.0)
    inertia_enabled: bool  = setting(True, label='Enable Inertia', description='Continue panning with momentum after release',   category='ui.canvas', order=41)
