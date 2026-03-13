"""
Built-in theme implementations.

DefaultTheme is a minimal framework-level workbench theme used as an emergency
fallback when ThemeRegistry is unavailable (e.g. before libraries have loaded).
The full Haywire dark/light themes live in haybale-core.
"""

from haywire.ui.themes.workbench import WorkbenchTheme
from haywire.ui.themes.decorator import theme


# ============================================================================
# Framework fallback WorkbenchTheme
#
# Used only when ThemeRegistry is unavailable (app_shell emergency path).
# The canonical Haywire themes (haywire-dark, haywire-light, default node
# theme) are registered by haybale-core via its register_components().
# ============================================================================

@theme(id='haywire-default', label='Default Theme')
class DefaultTheme(WorkbenchTheme):
    """
    Minimal dark fallback used by app_shell when ThemeRegistry is not yet
    available.  Mirrors the haywire-dark palette so the UI looks correct on
    first paint even before libraries have loaded.
    """

    bg_page     = '#12121e'
    bg_surface  = '#1e1e2e'
    bg_sidebar  = '#181825'
    bg_elevated = '#2a2a3e'
    bg_overlay  = 'rgba(0,0,0,0.5)'
    bg_input    = '#16162a'

    border       = '#333333'
    border_strong = '#4a4a6a'

    text_body      = 'rgba(255,255,255,0.87)'
    text_muted     = 'rgba(255,255,255,0.55)'
    text_dim       = 'rgba(255,255,255,0.6)'
    text_expansion = 'rgba(255,255,255,0.8)'
    text_on_accent = '#ffffff'

    accent        = '#4f8ef7'
    accent_hover  = '#7080ff'
    accent_active = '#3060d0'

    danger  = '#f44336'
    warning = '#ff9800'
    success = '#4caf50'
    info    = '#2196f3'

    node_bg          = '#1e1e2e'
    node_border      = '#2e2e48'
    node_header_bg   = '#252540'
    node_header_text = 'rgba(255,255,255,0.87)'
    node_selected    = '#4f8ef7'
    node_shadow      = 'rgba(0,0,0,0.4)'

    edge_default  = '#4a4a6a'
    edge_selected = '#4f8ef7'

    canvas_bg   = '#0e0e1a'
    canvas_grid = '#1a1a2e'

    topbar_bg   = '#12121e'
    topbar_text = 'rgba(255,255,255,0.87)'

    sidebar_bg          = '#0e0e1a'
    sidebar_icon        = '#6060a0'
    sidebar_icon_active = '#4f8ef7'

    panel_bg   = '#1a1a2c'
    panel_text = '#c0c0e0'

    statusbar_bg   = '#1e3a5f'
    statusbar_text = 'rgba(255,255,255,0.7)'

    console_bg   = '#0d1117'
    console_text = '#4ade80'
