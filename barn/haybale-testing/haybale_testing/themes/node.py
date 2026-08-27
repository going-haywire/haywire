"""
Minimal node-flavoured theme fixture for testing the theme system.
"""

from haywire.ui.themes.workbench import BaseTheme
from haywire.ui.themes.decorator import theme


@theme(theme_type="node", label="Test Node", hidden=True)
class TestNodeTheme(BaseTheme):
    """Minimal node theme for tests.

    Deliberately distinctive values: tests assert that selecting this theme
    changes the emitted vars, so every token differs from the shipped themes.
    """

    node_bg = "#123456"
    node_border_color = "#234567"
    node_border_width = "5px"
    node_border_radius = "4px"
    node_header_bg = "#abcdef"
    node_header_text_color = "#ffffff"
    node_text_color = "#eeeeee"
