# haywire/core/settings/builtins/ui_edge.py
"""UI Edge appearance settings."""

from ..schema import GlobalSettings
from ..types import Color
from ..descriptors import setting


class EdgeUISettings(GlobalSettings, namespace='ui.edge'):
    """Global settings controlling edge (connection) appearance."""

    # Colors
    color:          Color = setting('#666666', label='Edge Color',         description='Default color for edges',                   category='ui.edge', order=10, widget='color')
    color_selected: Color = setting('#1976d2', label='Selected Edge Color', description='Color when edge is selected',             category='ui.edge', order=11, widget='color')
    color_invalid:  Color = setting('#f44336', label='Invalid Edge Color',  description='Color for invalid connections',           category='ui.edge', order=12, widget='color')
    color_hover:    Color = setting('#42a5f5', label='Hover Edge Color',    description='Color when hovering over edge',           category='ui.edge', order=13, widget='color')
    use_port_colors: bool = setting(True,      label='Use Port Colors',     description='Color edges based on connected port types', category='ui.edge', order=14)

    # Line style
    width:          int = setting(2, label='Edge Width',          description='Default edge width in pixels', category='ui.edge', order=20, min=1, max=8)
    width_selected: int = setting(3, label='Selected Edge Width', description='Edge width when selected',     category='ui.edge', order=21, min=1, max=10)

    # Curve
    curve_style:   str   = setting('bezier', label='Curve Style',   description='How edges are drawn between nodes', category='ui.edge', order=30, choices=['bezier', 'straight', 'step', 'smoothstep'])
    curve_tension: float = setting(0.5,      label='Curve Tension', description='Tension for bezier curves (0-1)',  category='ui.edge', order=31, min=0.0, max=1.0)
    curve_offset:  int   = setting(50,       label='Curve Offset',  description='Control point offset for curves', category='ui.edge', order=32, min=10, max=200)

    # Animation
    animate_flow:       bool  = setting(False, label='Animate Flow',       description='Show animated flow direction on edges', category='ui.edge', order=40)
    animation_speed:    float = setting(1.0,   label='Animation Speed',    description='Speed of flow animation',              category='ui.edge', order=41, min=0.1, max=5.0)
    animate_on_execute: bool  = setting(True,  label='Animate on Execute', description='Animate edges during execution',       category='ui.edge', order=42)
