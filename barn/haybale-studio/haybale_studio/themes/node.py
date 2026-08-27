"""
Haywire built-in node theme — the default node rendering appearance.

Hot-reloadable: edit this file in an editable install and ThemeRegistry
will update automatically on the next library reload cycle.
"""

from haywire.ui.themes.workbench import BaseTheme
from haywire.ui.themes.decorator import theme


@theme(theme_type="node", label="Default Node Theme")
class DefaultNodeTheme(BaseTheme):
    """Default node rendering theme — works on both dark and light backgrounds.

    Values match the dark workbench theme, so selecting this theme changes
    nothing on its own — it is the baseline a custom node theme is written
    against.
    """

    node_bg = "linear-gradient(135deg, #ff0000 0%, #ff00ff 100%)"
    node_border_color = "#333333"
    node_border_width = "2px"
    node_border_radius = "16px"
    node_header_bg = "#252540"
    node_header_text_color = "#e8e8f4"
    node_text_color = "#ffffff"

    # Text
    text_body = "rgba(255,255,255,0.87)"
    text_muted = "rgba(255,255,255,0.55)"
    text_dim = "rgba(255,255,255,0.6)"
    text_expansion = "rgba(255,255,255,0.8)"
    text_on_accent = "#ffffff"

    # Backgrounds
    bg_page = "#12121e"
    bg_surface = "#1e1e2e"
    bg_sidebar = "#181825"
    bg_elevated = "#2a2a3e"
    bg_overlay = "rgba(0,0,0,0.5)"
    bg_input = "linear-gradient(135deg, #ff00ff 0%, #ff0000 100%)"
    bg_hover = "#1e1e2e"
    bg_active = "#2a2a4a"

    # Borders
    border = "#333333"
    border_strong = "#4a4a6a"
