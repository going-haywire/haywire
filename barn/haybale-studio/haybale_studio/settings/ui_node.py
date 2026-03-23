# haybale_studio/settings/ui_node.py
"""Node layout and visibility settings (colors are owned by the theme system)."""

from haywire.core.settings.schema import GlobalSettings
from haywire.core.settings import setting
from haywire.core.settings.decorator import settings


@settings(namespace='ui.node', label='Node UI')
class NodeUISettings(GlobalSettings):
    """Global settings controlling node layout, dimensions, and label visibility."""

    # Label and hint visibility
    show_labels:     bool = setting(True, label='Show Port Labels', description='Display labels next to ports',       category='ui.node', order=10)
    show_type_hints: bool = setting(True, label='Show Type Hints',  description='Display type information on ports', category='ui.node', order=11)
    show_tooltips:   bool = setting(True, label='Show Tooltips',    description='Display tooltips on hover',         category='ui.node', order=12)

    # Dimensions
    min_width:     int = setting(150, label='Minimum Width',  description='Minimum node width in pixels',               category='ui.node', order=20, min=50,  max=500)
    max_width:     int = setting(400, label='Maximum Width',  description='Maximum node width in pixels (0=unlimited)', category='ui.node', order=21, min=0,   max=1000)
    header_height: int = setting(32,  label='Header Height',  description='Height of node header in pixels',            category='ui.node', order=22, min=20,  max=60)
    port_spacing:  int = setting(24,  label='Port Spacing',   description='Vertical spacing between ports in pixels',   category='ui.node', order=23, min=16,  max=48)

    # Typography
    font_size:         int = setting(12,                             label='Font Size',         description='Default font size for node text', category='ui.node', order=30, min=8, max=24)
    font_family:       str = setting('Inter, system-ui, sans-serif', label='Font Family',       description='Font family for node text',       category='ui.node', order=31)
    title_font_weight: int = setting(600,                            label='Title Font Weight', description='Font weight for node titles',      category='ui.node', order=32, choices=[400, 500, 600, 700])

    # Shadow
    shadow_enabled: bool = setting(True, label='Enable Shadow', description='Show drop shadow behind nodes', category='ui.node', order=40)
