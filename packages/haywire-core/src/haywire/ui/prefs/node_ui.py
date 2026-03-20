# haywire/ui/prefs/node_ui.py
"""Node layout and visibility preference singleton."""

from haywire.core.reactive import Reactive, prop


class NodeUISettings(Reactive):
    """Global preferences controlling node layout, dimensions, and label visibility."""

    # Label and hint visibility
    show_labels:     bool = prop(True, label='Show Port Labels', description='Display labels next to ports',       category='ui.node', order=10)
    show_type_hints: bool = prop(True, label='Show Type Hints',  description='Display type information on ports', category='ui.node', order=11)
    show_tooltips:   bool = prop(True, label='Show Tooltips',    description='Display tooltips on hover',         category='ui.node', order=12)

    # Dimensions
    min_width:     int = prop(150, label='Minimum Width',  description='Minimum node width in pixels',               category='ui.node', order=20, min=50,  max=500)
    max_width:     int = prop(400, label='Maximum Width',  description='Maximum node width in pixels (0=unlimited)', category='ui.node', order=21, min=0,   max=1000)
    header_height: int = prop(32,  label='Header Height',  description='Height of node header in pixels',            category='ui.node', order=22, min=20,  max=60)
    port_spacing:  int = prop(24,  label='Port Spacing',   description='Vertical spacing between ports in pixels',   category='ui.node', order=23, min=16,  max=48)

    # Typography
    font_size:         int = prop(12,                             label='Font Size',         description='Default font size for node text', category='ui.node', order=30, min=8, max=24)
    font_family:       str = prop('Inter, system-ui, sans-serif', label='Font Family',       description='Font family for node text',       category='ui.node', order=31)
    title_font_weight: int = prop(600,                            label='Title Font Weight', description='Font weight for node titles',      category='ui.node', order=32, choices=[400, 500, 600, 700])

    # Shadow
    shadow_enabled: bool = prop(True, label='Enable Shadow', description='Show drop shadow behind nodes', category='ui.node', order=40)
