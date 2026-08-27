"""
Haywire built-in workbench themes — dark and light variants.

These are the official Haywire themes shipped with haybale-core. They are
hot-reloadable: edit this file in an editable install and the ThemeRegistry
will update automatically on the next library reload cycle.
"""

from haywire.ui.themes.workbench import BaseTheme
from haywire.ui.themes.decorator import theme


@theme(theme_type="workbench", label="Haywire Dark")
class HaywireDarkTheme(BaseTheme):
    """Default dark workbench theme."""

    # Backgrounds
    bg_page = "#12121e"
    bg_surface = "#1e1e2e"
    bg_sidebar = "#181825"
    bg_elevated = "#2a2a3e"
    bg_overlay = "rgba(0,0,0,0.5)"
    bg_input = "#16162a"
    bg_hover = "#1e1e2e"
    bg_active = "#2a2a4a"

    # Borders
    border = "#333333"
    border_strong = "#4a4a6a"

    # Text
    text_body = "rgba(255,255,255,0.87)"
    text_muted = "rgba(255,255,255,0.55)"
    text_dim = "rgba(255,255,255,0.6)"
    text_expansion = "rgba(255,255,255,0.8)"
    text_on_accent = "#ffffff"

    # Accent
    accent = "#4f8ef7"
    accent_hover = "#7080ff"
    accent_active = "#3060d0"

    # Status
    danger = "#f44336"
    warning = "#ff9800"
    warning_dim = "rgba(255,152,0,0.55)"
    success = "#4caf50"
    info = "#2196f3"
    positive = "#4caf50"

    # Node chrome — Tier 1 (card surface; overridable per graph and per node).
    #
    # The border values are seeded from what DefaultNodeSkin hardcoded, not from
    # the old `node_border = "#2e2e48"`: that token existed but no skin ever read
    # it, so honouring it would restyle every node to a colour nobody has seen.
    node_bg = "#1e1e2e"
    node_border_color = "#333333"
    node_border_width = "3px"
    node_border_radius = "16px"
    node_header_bg = "#252540"
    node_header_text_color = "rgba(255,255,255,0.87)"
    node_text_color = "#c0c0e0"
    # Tier 2 (canvas affordances; global/graph tier only — see theme-canon).
    node_selected = "#4f8ef7"
    node_active = "#8fb8ff"
    node_shadow = "rgba(0,0,0,0.4)"

    # Edges
    edge_default = "#4a4a6a"
    edge_selected = "#4f8ef7"
    edge_active = "#8fb8ff"

    # Canvas
    canvas_bg = "#0e0e1a"
    canvas_grid = "#1a1a2e"
    ghost_pin = "rgba(128,128,128,0.15)"
    danger_bg = "rgba(244,67,54,0.08)"

    # TopBar
    topbar_bg = "#12121e"
    topbar_text = "rgba(255,255,255,0.87)"

    # Sidebar / ActivityBar
    sidebar_bg = "#0e0e1a"
    sidebar_icon = "#6060a0"
    sidebar_icon_active = "#4f8ef7"

    # Panel
    panel_bg = "#1a1a2c"
    panel_text = "#c0c0e0"
    panel_header_0_bg = "#1e1e30"
    panel_header_1_bg = "transparent"

    # StatusBar
    statusbar_bg = "#1e3a5f"
    statusbar_text = "rgba(255,255,255,0.7)"

    # Console
    console_bg = "#0d1117"
    console_text = "#4ade80"

    # Compact fields
    compact_gap = "0.25rem"
    compact_field_h = "26px"
    compact_row_min_h = "28px"

    # Popups / drag
    popup_shadow = "0 8px 32px rgba(0,0,0,0.5)"
    drag_over = "#4f8ef7"
    drag_ghost = "0.5"


@theme(theme_type="workbench", label="Haywire Light")
class HaywireLightTheme(BaseTheme):
    """Default light workbench theme."""

    # Backgrounds
    bg_page = "#f8f8fc"
    bg_surface = "#e8e8f0"
    bg_sidebar = "#f0f0f8"
    bg_elevated = "#f0f0f6"
    bg_overlay = "rgba(0,0,0,0.3)"
    bg_input = "#f8f8fc"
    bg_hover = "#e8e8f0"
    bg_active = "#d0d0e8"

    # Borders
    border = "rgba(0,0,0,0.15)"
    border_strong = "#a0a0c0"

    # Text
    text_body = "rgba(0,0,0,0.87)"
    text_muted = "rgba(0,0,0,0.55)"
    text_dim = "rgba(0,0,0,0.6)"
    text_expansion = "rgba(0,0,0,0.8)"
    text_on_accent = "#ffffff"

    # Accent
    accent = "#4f8ef7"
    accent_hover = "#6090ff"
    accent_active = "#3060d0"

    # Status
    danger = "#d32f2f"
    warning = "#f57c00"
    warning_dim = "rgba(245,124,0,0.55)"
    success = "#388e3c"
    info = "#1976d2"
    positive = "#388e3c"

    # Node chrome — Tier 1 (card surface; overridable per graph and per node).
    #
    # Border seeded from DefaultNodeSkin's literal, as in the dark theme: the
    # old `node_border = "#ffffff"` was never read by any skin.
    node_bg = "rgba(255,255,255,0.3)"
    node_border_color = "#333333"
    node_border_width = "3px"
    node_border_radius = "16px"
    node_header_bg = "#f0f0f6"
    node_header_text_color = "rgba(0,0,0,0.87)"
    node_text_color = "rgba(0,0,0,0.87)"
    # Tier 2 (canvas affordances; global/graph tier only — see theme-canon).
    node_selected = "#4f8ef7"
    node_active = "#1f5fd0"
    node_shadow = "rgba(0,0,0,0.08)"

    # Edges
    edge_default = "#a0a0c0"
    edge_selected = "#4f8ef7"
    edge_active = "#1f5fd0"

    # Canvas
    canvas_bg = "#1e1e1e"
    canvas_grid = "#2d2d2d"
    ghost_pin = "rgba(0,0,0,0.12)"
    danger_bg = "rgba(211,47,47,0.06)"

    # TopBar
    topbar_bg = "#ffffff"
    topbar_text = "rgba(0,0,0,0.87)"

    # Sidebar / ActivityBar
    sidebar_bg = "#f0f0f8"
    sidebar_icon = "#8080b0"
    sidebar_icon_active = "#4f8ef7"

    # Panel
    panel_bg = "#ffffff"
    panel_text = "rgba(0,0,0,0.87)"
    panel_header_0_bg = "#f5f5fa"
    panel_header_1_bg = "transparent"

    # StatusBar
    statusbar_bg = "#1565c0"
    statusbar_text = "rgba(255,255,255,0.87)"

    # Console
    console_bg = "#f0f0f0"
    console_text = "rgba(0,0,0,0.87)"

    # Compact fields
    compact_gap = "0.25rem"
    compact_field_h = "26px"
    compact_row_min_h = "28px"

    # Popups / drag
    popup_shadow = "0 8px 32px rgba(0,0,0,0.18)"
    drag_over = "#4f8ef7"
    drag_ghost = "0.5"
