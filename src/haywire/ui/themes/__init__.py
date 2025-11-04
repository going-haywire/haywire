"""
Haywire Theme System

Provides theming support with built-in and user-defined themes.
Features:
- Built-in themes with IDE color preview
- TOML-based user themes
- Theme inheritance
- Hot-reload via observer pattern
- Type-safe color access
- Color utilities
"""

from haywire.ui.themes.colors import Colors
from haywire.ui.themes.palette import ThemePalette
from haywire.ui.themes.base import ThemeMetadata
from haywire.ui.themes.utils import ColorUtils
from haywire.ui.themes.colors import Theme_UI_Color
from haywire.ui.themes.loader import ThemeValidationError

__all__ = [
    # Named color constants
    'Colors',
    
    # Theme management
    'ThemePalette',
    
    # Types and enums
    'ThemeMetadata',
    'Theme_UI_Color',
    
    # Utilities
    'ColorUtils',
    
    # Exceptions
    'ThemeValidationError',
]
