# haywire/core/settings/builtins/ui_edge.py
"""
UI Edge appearance settings.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..registry import GlobalSettingsRegistry


CATEGORY = 'ui.edge'


def register(registry: 'GlobalSettingsRegistry') -> None:
    """Register edge appearance settings."""
    
    # Colors
    registry.define(
        'ui.edge.color', '#666666',
        label='Edge Color',
        description='Default color for edges',
        category=CATEGORY,
        ui_widget='color',
        ui_order=10
    )
    registry.define(
        'ui.edge.color_selected', '#1976d2',
        label='Selected Edge Color',
        description='Color when edge is selected',
        category=CATEGORY,
        ui_widget='color',
        ui_order=11
    )
    registry.define(
        'ui.edge.color_invalid', '#f44336',
        label='Invalid Edge Color',
        description='Color for invalid connections',
        category=CATEGORY,
        ui_widget='color',
        ui_order=12
    )
    registry.define(
        'ui.edge.color_hover', '#42a5f5',
        label='Hover Edge Color',
        description='Color when hovering over edge',
        category=CATEGORY,
        ui_widget='color',
        ui_order=13
    )
    registry.define(
        'ui.edge.use_port_colors', True,
        label='Use Port Colors',
        description='Color edges based on connected port types',
        category=CATEGORY,
        ui_order=14
    )
    
    # Line style
    registry.define(
        'ui.edge.width', 2,
        label='Edge Width',
        description='Default edge width in pixels',
        category=CATEGORY,
        min_value=1,
        max_value=8,
        ui_order=20
    )
    registry.define(
        'ui.edge.width_selected', 3,
        label='Selected Edge Width',
        description='Edge width when selected',
        category=CATEGORY,
        min_value=1,
        max_value=10,
        ui_order=21
    )
    
    # Curve
    registry.define(
        'ui.edge.curve_style', 'bezier',
        label='Curve Style',
        description='How edges are drawn between nodes',
        category=CATEGORY,
        choices=['bezier', 'straight', 'step', 'smoothstep'],
        ui_order=30
    )
    registry.define(
        'ui.edge.curve_tension', 0.5,
        label='Curve Tension',
        description='Tension for bezier curves (0-1)',
        category=CATEGORY,
        min_value=0.0,
        max_value=1.0,
        ui_order=31
    )
    registry.define(
        'ui.edge.curve_offset', 50,
        label='Curve Offset',
        description='Control point offset for curves',
        category=CATEGORY,
        min_value=10,
        max_value=200,
        ui_order=32
    )
    
    # Animation
    registry.define(
        'ui.edge.animate_flow', False,
        label='Animate Flow',
        description='Show animated flow direction on edges',
        category=CATEGORY,
        ui_order=40
    )
    registry.define(
        'ui.edge.animation_speed', 1.0,
        label='Animation Speed',
        description='Speed of flow animation',
        category=CATEGORY,
        min_value=0.1,
        max_value=5.0,
        ui_order=41
    )
    registry.define(
        'ui.edge.animate_on_execute', True,
        label='Animate on Execute',
        description='Animate edges during execution',
        category=CATEGORY,
        ui_order=42
    )