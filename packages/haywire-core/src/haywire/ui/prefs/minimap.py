# haywire/ui/prefs/minimap.py
"""Minimap layout and visibility preference singleton."""

from haywire.core.property import Bag, prop


class MinimapSettings(Bag):
    """Global preferences controlling the minimap overlay layout and visibility."""

    enabled:       bool  = prop(True,          label='Show Minimap',       description='Display minimap overview',                         category='ui.minimap', order=10)
    position:      str   = prop('bottom-right', label='Minimap Position',   description='Corner position of minimap',                       category='ui.minimap', order=11, choices=['top-left', 'top-right', 'bottom-left', 'bottom-right'])
    width:         int   = prop(200,            label='Minimap Width',      description='Width of minimap in pixels',                       category='ui.minimap', order=12, min=100, max=400)
    height:        int   = prop(150,            label='Minimap Height',     description='Height of minimap in pixels',                      category='ui.minimap', order=13, min=75,  max=300)
    opacity:       float = prop(0.85,           label='Minimap Opacity',    description='Opacity of the minimap',                           category='ui.minimap', order=14, min=0.3, max=1.0)
    show_on_hover: bool  = prop(False,          label='Show on Hover Only', description='Only show minimap when hovering near its position', category='ui.minimap', order=15)
