"""
Haywire built-in node theme — the default node rendering appearance.

Hot-reloadable: edit this file in an editable install and ThemeRegistry
will update automatically on the next library reload cycle.
"""

from haywire.ui.themes.node_theme import NodeTheme
from haywire.ui.themes.decorator import theme


@theme(label="Default Node Theme")
class DefaultNodeTheme(NodeTheme):
    """Default node rendering theme — works on both dark and light backgrounds.

    Declares the Tier 1 subset only. Values match the dark workbench theme, so
    selecting this theme changes nothing on its own — it is the baseline a
    custom node theme is written against.
    """

    node_bg = "#1e1e2e"
    node_border_color = "#333333"
    node_border_width = "3px"
    node_border_radius = "16px"
    node_header_bg = "#252540"
    node_header_text_color = "#e8e8f4"
    node_text_color = "#c0c0e0"
