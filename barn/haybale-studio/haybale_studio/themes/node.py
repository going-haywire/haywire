"""
Haywire built-in node theme — the default node rendering appearance.

Hot-reloadable: edit this file in an editable install and ThemeRegistry
will update automatically on the next library reload cycle.
"""

from haywire.ui.themes.node_theme import NodeTheme
from haywire.ui.themes.decorator import theme


@theme(label="Default Node Theme")
class DefaultNodeTheme(NodeTheme):
    """Default node rendering theme — works on both dark and light backgrounds."""

    header_bg = "#252540"
    header_text = "#e8e8f4"
    body_bg = "#1e1e2e"
    body_text = "#c0c0e0"
    border = "#2e2e48"
    border_selected = "#7c6af7"
    port_inlet = "#4a90d9"
    port_outlet = "#d94a4a"
    port_exec_inlet = "#ffffff"
    port_exec_outlet = "#ffffff"
    error_bg = "#3e1a1a"
    error_border = "#f44336"
    muted_opacity = "0.5"
