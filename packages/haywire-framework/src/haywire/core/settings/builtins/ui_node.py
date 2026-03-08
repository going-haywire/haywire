# haywire/core/settings/builtins/ui_node.py
"""UI Node appearance settings."""

from ..schema import GlobalSettings
from ..types import Color
from ..descriptors import setting


class NodeUISettings(GlobalSettings, namespace='ui.node'):
    """Global settings controlling node appearance."""

    # Background colors
    bg_color:           Color = setting('#ffffff', label='Background Color',       description='Default background color for nodes',             category='ui.node', order=10, widget='color')
    bg_color_selected:  Color = setting('#e3f2fd', label='Selected Background',    description='Background color when node is selected',          category='ui.node', order=11, widget='color')
    bg_color_error:     Color = setting('#ffebee', label='Error Background',       description='Background color when node has errors',           category='ui.node', order=12, widget='color')
    bg_color_executing: Color = setting('#fff3e0', label='Executing Background',   description='Background color while node is executing',        category='ui.node', order=13, widget='color')

    # Border
    border_color:          Color = setting('#cccccc', label='Border Color',         description='Default border color for nodes',                  category='ui.node', order=20, widget='color')
    border_color_selected: Color = setting('#1976d2', label='Selected Border',      description='Border color when node is selected',              category='ui.node', order=21, widget='color')
    border_width:           int  = setting(1,          label='Border Width',         description='Border width in pixels',                         category='ui.node', order=22, min=0, max=5)
    border_radius:          int  = setting(4,          label='Border Radius',        description='Corner radius in pixels',                        category='ui.node', order=23, min=0, max=20)

    # Typography
    font_size:         int = setting(12,                          label='Font Size',         description='Default font size for node text',       category='ui.node', order=30, min=8,  max=24)
    font_family:       str = setting('Inter, system-ui, sans-serif', label='Font Family',   description='Font family for node text',             category='ui.node', order=31)
    title_font_weight: int = setting(600,                         label='Title Font Weight', description='Font weight for node titles',           category='ui.node', order=32, choices=[400, 500, 600, 700])

    # Labels and hints
    show_labels:    bool = setting(True, label='Show Port Labels', description='Display labels next to ports',          category='ui.node', order=40)
    show_type_hints: bool = setting(True, label='Show Type Hints', description='Display type information on ports',     category='ui.node', order=41)
    show_tooltips:  bool = setting(True, label='Show Tooltips',   description='Display tooltips on hover',             category='ui.node', order=42)

    # Dimensions
    min_width:     int = setting(150, label='Minimum Width',  description='Minimum node width in pixels',      category='ui.node', order=50, min=50,  max=500)
    max_width:     int = setting(400, label='Maximum Width',  description='Maximum node width in pixels (0=unlimited)', category='ui.node', order=51, min=0, max=1000)
    header_height: int = setting(32,  label='Header Height',  description='Height of node header in pixels',   category='ui.node', order=52, min=20, max=60)
    port_spacing:  int = setting(24,  label='Port Spacing',   description='Vertical spacing between ports in pixels', category='ui.node', order=53, min=16, max=48)

    # Shadow
    shadow_enabled: bool  = setting(True,             label='Enable Shadow', description='Show drop shadow behind nodes', category='ui.node', order=60)
    shadow_color:   Color = setting('rgba(0,0,0,0.1)', label='Shadow Color',  description='Color of node shadow',          category='ui.node', order=61)
