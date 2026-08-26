"""
Haywire Theme System

Provides theming support via the single BaseTheme Python class, authored
with @theme(theme_type='workbench'|'node') and registered through the
ThemeRegistry DI singleton.

The canonical Haywire themes (haywire-dark, haywire-light) are defined in
haybale-core and registered via register_components().
"""

from haywire.ui.themes.workbench import BaseTheme
from haywire.ui.themes.registry import ThemeRegistry
from haywire.ui.themes.decorator import theme
from haywire.ui.themes.icons import ICONS

__all__ = [
    "BaseTheme",
    "ThemeRegistry",
    "theme",
    "ICONS",
]
