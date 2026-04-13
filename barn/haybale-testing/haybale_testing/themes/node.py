"""
Minimal NodeTheme fixture for testing the theme system.
"""

from haywire.ui.themes.node_theme import NodeTheme
from haywire.ui.themes.decorator import theme


@theme(label="Test Node")
class TestNodeTheme(NodeTheme):
    """Minimal node theme for tests."""

    header_bg = "#abcdef"
    header_text = "#ffffff"
    body_bg = "#123456"
    body_text = "#eeeeee"
    border = "#234567"
    border_selected = "#ff00ff"
    port_inlet = "#00aaff"
    port_outlet = "#ff6600"
    port_exec_inlet = "#ffffff"
    port_exec_outlet = "#ffffff"
    error_bg = "#330000"
    error_border = "#ff0000"
    muted_opacity = "0.4"
