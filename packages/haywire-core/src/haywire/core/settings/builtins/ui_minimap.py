# haywire/core/settings/builtins/ui_minimap.py
"""UI Minimap settings."""

from ..schema import GlobalSettings
from ..types import Color
from ..descriptors import setting


class MinimapUISettings(GlobalSettings, namespace='ui.minimap'):
    """Global settings controlling the minimap overlay."""

    enabled:       bool  = setting(True,           label='Show Minimap',        description='Display minimap overview',                        category='ui.minimap', order=10)
    position:      str   = setting('bottom-right',  label='Minimap Position',    description='Corner position of minimap',                      category='ui.minimap', order=11, choices=['top-left', 'top-right', 'bottom-left', 'bottom-right'])
    width:         int   = setting(200,             label='Minimap Width',       description='Width of minimap in pixels',                      category='ui.minimap', order=12, min=100, max=400)
    height:        int   = setting(150,             label='Minimap Height',      description='Height of minimap in pixels',                     category='ui.minimap', order=13, min=75,  max=300)
    opacity:       float = setting(0.85,            label='Minimap Opacity',     description='Opacity of the minimap',                          category='ui.minimap', order=14, min=0.3, max=1.0)
    show_on_hover: bool  = setting(False,           label='Show on Hover Only',  description='Only show minimap when hovering near its position', category='ui.minimap', order=15)
    node_color:    Color = setting('#4a90d9',        label='Node Color',          description='Color of nodes in minimap',                       category='ui.minimap', order=20, widget='color')
    viewport_color: Color = setting('rgba(255,255,255,0.2)', label='Viewport Color', description='Color of current viewport indicator',         category='ui.minimap', order=21)
