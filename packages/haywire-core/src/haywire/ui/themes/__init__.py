"""
Haywire Theme System

Provides theming support via WorkbenchTheme and NodeTheme Python classes,
registered through the ThemeRegistry DI singleton.

The canonical Haywire themes (haywire-dark, haywire-light) are defined in
haybale-core and registered via register_components().
"""

from haywire.ui.themes.workbench import WorkbenchTheme
from haywire.ui.themes.node_theme import NodeTheme
from haywire.ui.themes.registry import ThemeRegistry
from haywire.ui.themes.decorator import theme
from haywire.ui.themes.icons import ICONS

__all__ = [
    "WorkbenchTheme",
    "NodeTheme",
    "ThemeRegistry",
    "theme",
    "ICONS",
]
