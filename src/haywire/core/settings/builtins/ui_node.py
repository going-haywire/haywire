# haywire/core/settings/builtins/ui_node.py
"""
UI Node appearance settings.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..registry import GlobalSettingsRegistry


CATEGORY = 'ui.node'
"""Category for all settings in this module."""


def register(registry: 'GlobalSettingsRegistry') -> None:
    """Register node appearance settings."""
    
    # Background colors
    registry.define(
        'ui.node.bg_color', '#ffffff',
        label='Background Color',
        description='Default background color for nodes',
        category=CATEGORY,
        ui_widget='color',
        ui_order=10
    )
    registry.define(
        'ui.node.bg_color_selected', '#e3f2fd',
        label='Selected Background',
        description='Background color when node is selected',
        category=CATEGORY,
        ui_widget='color',
        ui_order=11
    )
    registry.define(
        'ui.node.bg_color_error', '#ffebee',
        label='Error Background',
        description='Background color when node has errors',
        category=CATEGORY,
        ui_widget='color',
        ui_order=12
    )
    registry.define(
        'ui.node.bg_color_executing', '#fff3e0',
        label='Executing Background',
        description='Background color while node is executing',
        category=CATEGORY,
        ui_widget='color',
        ui_order=13
    )
    
    # Border
    registry.define(
        'ui.node.border_color', '#cccccc',
        label='Border Color',
        description='Default border color for nodes',
        category=CATEGORY,
        ui_widget='color',
        ui_order=20
    )
    registry.define(
        'ui.node.border_color_selected', '#1976d2',
        label='Selected Border',
        description='Border color when node is selected',
        category=CATEGORY,
        ui_widget='color',
        ui_order=21
    )
    registry.define(
        'ui.node.border_width', 1,
        label='Border Width',
        description='Border width in pixels',
        category=CATEGORY,
        min_value=0,
        max_value=5,
        ui_order=22
    )
    registry.define(
        'ui.node.border_radius', 4,
        label='Border Radius',
        description='Corner radius in pixels',
        category=CATEGORY,
        min_value=0,
        max_value=20,
        ui_order=23
    )
    
    # Typography
    registry.define(
        'ui.node.font_size', 12,
        label='Font Size',
        description='Default font size for node text',
        category=CATEGORY,
        min_value=8,
        max_value=24,
        ui_order=30
    )
    registry.define(
        'ui.node.font_family', 'Inter, system-ui, sans-serif',
        label='Font Family',
        description='Font family for node text',
        category=CATEGORY,
        ui_order=31
    )
    registry.define(
        'ui.node.title_font_weight', 600,
        label='Title Font Weight',
        description='Font weight for node titles',
        category=CATEGORY,
        choices=[400, 500, 600, 700],
        ui_order=32
    )
    
    # Labels and hints
    registry.define(
        'ui.node.show_labels', True,
        label='Show Port Labels',
        description='Display labels next to ports',
        category=CATEGORY,
        ui_order=40
    )
    registry.define(
        'ui.node.show_type_hints', True,
        label='Show Type Hints',
        description='Display type information on ports',
        category=CATEGORY,
        ui_order=41
    )
    registry.define(
        'ui.node.show_tooltips', True,
        label='Show Tooltips',
        description='Display tooltips on hover',
        category=CATEGORY,
        ui_order=42
    )
    
    # Dimensions
    registry.define(
        'ui.node.min_width', 150,
        label='Minimum Width',
        description='Minimum node width in pixels',
        category=CATEGORY,
        min_value=50,
        max_value=500,
        ui_order=50
    )
    registry.define(
        'ui.node.max_width', 400,
        label='Maximum Width',
        description='Maximum node width in pixels (0 = unlimited)',
        category=CATEGORY,
        min_value=0,
        max_value=1000,
        ui_order=51
    )
    registry.define(
        'ui.node.header_height', 32,
        label='Header Height',
        description='Height of node header in pixels',
        category=CATEGORY,
        min_value=20,
        max_value=60,
        ui_order=52
    )
    registry.define(
        'ui.node.port_spacing', 24,
        label='Port Spacing',
        description='Vertical spacing between ports in pixels',
        category=CATEGORY,
        min_value=16,
        max_value=48,
        ui_order=53
    )
    
    # Shadow
    registry.define(
        'ui.node.shadow_enabled', True,
        label='Enable Shadow',
        description='Show drop shadow behind nodes',
        category=CATEGORY,
        ui_order=60
    )
    registry.define(
        'ui.node.shadow_color', 'rgba(0,0,0,0.1)',
        label='Shadow Color',
        description='Color of node shadow',
        category=CATEGORY,
        ui_order=61
    )