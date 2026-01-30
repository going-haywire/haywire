# haywire/core/settings/builtins/ui_minimap.py
"""
UI Minimap settings.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..registry import GlobalSettingsRegistry


CATEGORY = 'ui.minimap'


def register(registry: 'GlobalSettingsRegistry') -> None:
    """Register minimap settings."""
    
    registry.define(
        'ui.minimap.enabled', True,
        label='Show Minimap',
        description='Display minimap overview',
        category=CATEGORY,
        ui_order=10
    )
    registry.define(
        'ui.minimap.position', 'bottom-right',
        label='Minimap Position',
        description='Corner position of minimap',
        category=CATEGORY,
        choices=['top-left', 'top-right', 'bottom-left', 'bottom-right'],
        ui_order=11
    )
    registry.define(
        'ui.minimap.width', 200,
        label='Minimap Width',
        description='Width of minimap in pixels',
        category=CATEGORY,
        min_value=100,
        max_value=400,
        ui_order=12
    )
    registry.define(
        'ui.minimap.height', 150,
        label='Minimap Height',
        description='Height of minimap in pixels',
        category=CATEGORY,
        min_value=75,
        max_value=300,
        ui_order=13
    )
    registry.define(
        'ui.minimap.opacity', 0.85,
        label='Minimap Opacity',
        description='Opacity of the minimap',
        category=CATEGORY,
        min_value=0.3,
        max_value=1.0,
        ui_order=14
    )
    registry.define(
        'ui.minimap.show_on_hover', False,
        label='Show on Hover Only',
        description='Only show minimap when hovering near its position',
        category=CATEGORY,
        ui_order=15
    )
    registry.define(
        'ui.minimap.node_color', '#4a90d9',
        label='Node Color',
        description='Color of nodes in minimap',
        category=CATEGORY,
        ui_widget='color',
        ui_order=20
    )
    registry.define(
        'ui.minimap.viewport_color', 'rgba(255,255,255,0.2)',
        label='Viewport Color',
        description='Color of current viewport indicator',
        category=CATEGORY,
        ui_order=21
    )