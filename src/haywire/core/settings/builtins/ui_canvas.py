# haywire/core/settings/builtins/ui_canvas.py
"""
UI Canvas/graph background settings.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..registry import GlobalSettingsRegistry


CATEGORY = 'ui.canvas'


def register(registry: 'GlobalSettingsRegistry') -> None:
    """Register canvas appearance settings."""
    
    # Background
    registry.define(
        'ui.canvas.bg_color', '#1e1e1e',
        label='Canvas Background',
        description='Background color of the graph canvas',
        category=CATEGORY,
        ui_widget='color',
        ui_order=10
    )
    registry.define(
        'ui.canvas.bg_pattern', 'dots',
        label='Background Pattern',
        description='Pattern style for canvas background',
        category=CATEGORY,
        choices=['none', 'dots', 'lines', 'cross'],
        ui_order=11
    )
    
    # Grid
    registry.define(
        'ui.canvas.grid_enabled', True,
        label='Show Grid',
        description='Display grid on canvas',
        category=CATEGORY,
        ui_order=20
    )
    registry.define(
        'ui.canvas.grid_size', 20,
        label='Grid Size',
        description='Grid cell size in pixels',
        category=CATEGORY,
        min_value=5,
        max_value=100,
        ui_order=21
    )
    registry.define(
        'ui.canvas.grid_color', '#2d2d2d',
        label='Grid Color',
        description='Color of grid lines',
        category=CATEGORY,
        ui_widget='color',
        ui_order=22
    )
    registry.define(
        'ui.canvas.grid_subdivisions', 5,
        label='Grid Subdivisions',
        description='Number of minor grid lines per major line',
        category=CATEGORY,
        min_value=1,
        max_value=10,
        ui_order=23
    )
    registry.define(
        'ui.canvas.snap_to_grid', True,
        label='Snap to Grid',
        description='Snap nodes to grid when moving',
        category=CATEGORY,
        ui_order=24
    )
    
    # Zoom
    registry.define(
        'ui.canvas.zoom_min', 0.1,
        label='Minimum Zoom',
        description='Minimum zoom level',
        category=CATEGORY,
        min_value=0.05,
        max_value=0.5,
        ui_order=30
    )
    registry.define(
        'ui.canvas.zoom_max', 4.0,
        label='Maximum Zoom',
        description='Maximum zoom level',
        category=CATEGORY,
        min_value=1.0,
        max_value=10.0,
        ui_order=31
    )
    registry.define(
        'ui.canvas.zoom_speed', 0.1,
        label='Zoom Speed',
        description='Zoom sensitivity for scroll wheel',
        category=CATEGORY,
        min_value=0.01,
        max_value=0.5,
        ui_order=32
    )
    registry.define(
        'ui.canvas.zoom_to_cursor', True,
        label='Zoom to Cursor',
        description='Zoom centered on cursor position',
        category=CATEGORY,
        ui_order=33
    )
    
    # Pan
    registry.define(
        'ui.canvas.pan_speed', 1.0,
        label='Pan Speed',
        description='Panning speed multiplier',
        category=CATEGORY,
        min_value=0.1,
        max_value=3.0,
        ui_order=40
    )
    registry.define(
        'ui.canvas.inertia_enabled', True,
        label='Enable Inertia',
        description='Continue panning with momentum after release',
        category=CATEGORY,
        ui_order=41
    )