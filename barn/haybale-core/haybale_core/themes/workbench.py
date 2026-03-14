"""
Haywire built-in workbench themes — dark and light variants.

These are the official Haywire themes shipped with haybale-core. They are
hot-reloadable: edit this file in an editable install and the ThemeRegistry
will update automatically on the next library reload cycle.
"""

from haywire.ui.themes.workbench import WorkbenchTheme
from haywire.ui.themes.decorator import theme


@theme(registry_id='haywire-dark', label='Haywire Dark')
class HaywireDarkTheme(WorkbenchTheme):
    """Default dark workbench theme."""

    # Backgrounds
    bg_page     = '#12121e'
    bg_surface  = '#1e1e2e'
    bg_sidebar  = '#181825'
    bg_elevated = '#2a2a3e'
    bg_overlay  = 'rgba(0,0,0,0.5)'
    bg_input    = '#16162a'

    # Borders
    border       = '#333333'
    border_strong = '#4a4a6a'

    # Text
    text_body      = 'rgba(255,255,255,0.87)'
    text_muted     = 'rgba(255,255,255,0.55)'
    text_dim       = 'rgba(255,255,255,0.6)'
    text_expansion = 'rgba(255,255,255,0.8)'
    text_on_accent = '#ffffff'

    # Accent
    accent        = '#4f8ef7'
    accent_hover  = '#7080ff'
    accent_active = '#3060d0'

    # Status
    danger  = '#f44336'
    warning = '#ff9800'
    success = '#4caf50'
    info    = '#2196f3'

    # Node chrome
    node_bg          = '#1e1e2e'
    node_border      = '#2e2e48'
    node_header_bg   = '#252540'
    node_header_text = 'rgba(255,255,255,0.87)'
    node_selected    = '#4f8ef7'
    node_shadow      = 'rgba(0,0,0,0.4)'

    # Edges
    edge_default  = '#4a4a6a'
    edge_selected = '#4f8ef7'

    # Canvas
    canvas_bg   = '#0e0e1a'
    canvas_grid = '#1a1a2e'

    # TopBar
    topbar_bg   = '#12121e'
    topbar_text = 'rgba(255,255,255,0.87)'

    # Sidebar / ActivityBar
    sidebar_bg          = '#0e0e1a'
    sidebar_icon        = '#6060a0'
    sidebar_icon_active = '#4f8ef7'

    # Panel
    panel_bg   = '#1a1a2c'
    panel_text = '#c0c0e0'

    # StatusBar
    statusbar_bg   = '#1e3a5f'
    statusbar_text = 'rgba(255,255,255,0.7)'

    # Console
    console_bg   = '#0d1117'
    console_text = '#4ade80'


@theme(registry_id='haywire-light', label='Haywire Light')
class HaywireLightTheme(WorkbenchTheme):
    """Default light workbench theme."""

    # Backgrounds
    bg_page     = '#f8f8fc'
    bg_surface  = '#e8e8f0'
    bg_sidebar  = '#f0f0f8'
    bg_elevated = '#f0f0f6'
    bg_overlay  = 'rgba(0,0,0,0.3)'
    bg_input    = '#f8f8fc'

    # Borders
    border       = 'rgba(0,0,0,0.15)'
    border_strong = '#a0a0c0'

    # Text
    text_body      = 'rgba(0,0,0,0.87)'
    text_muted     = 'rgba(0,0,0,0.55)'
    text_dim       = 'rgba(0,0,0,0.6)'
    text_expansion = 'rgba(0,0,0,0.8)'
    text_on_accent = '#ffffff'

    # Accent
    accent        = '#4f8ef7'
    accent_hover  = '#6090ff'
    accent_active = '#3060d0'

    # Status
    danger  = '#d32f2f'
    warning = '#f57c00'
    success = '#388e3c'
    info    = '#1976d2'

    # Node chrome
    node_bg          = 'rgba(255,255,255,0.3)'
    node_border      = '#ffffff'
    node_header_bg   = '#f0f0f6'
    node_header_text = 'rgba(0,0,0,0.87)'
    node_selected    = '#4f8ef7'
    node_shadow      = 'rgba(0,0,0,0.08)'

    # Edges
    edge_default  = '#a0a0c0'
    edge_selected = '#4f8ef7'

    # Canvas
    canvas_bg   = '#1e1e1e'
    canvas_grid = '#2d2d2d'

    # TopBar
    topbar_bg   = '#ffffff'
    topbar_text = 'rgba(0,0,0,0.87)'

    # Sidebar / ActivityBar
    sidebar_bg          = '#f0f0f8'
    sidebar_icon        = '#8080b0'
    sidebar_icon_active = '#4f8ef7'

    # Panel
    panel_bg   = '#ffffff'
    panel_text = 'rgba(0,0,0,0.87)'

    # StatusBar
    statusbar_bg   = '#1565c0'
    statusbar_text = 'rgba(255,255,255,0.87)'

    # Console
    console_bg   = '#f0f0f0'
    console_text = 'rgba(0,0,0,0.87)'
