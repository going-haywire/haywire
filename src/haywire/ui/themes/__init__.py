"""
Haywire Theme System

Provides theming support with built-in and user-defined themes.
Features:
- Built-in themes with IDE color preview
- TOML-based user themes
- Theme inheritance
- Hot-reload via observer pattern
- Unified get() API with preference and fallback support
- Color utilities
"""

from haywire.ui.themes.keys import ThemeKey
from haywire.ui.themes.colors import Colors
from haywire.ui.themes.palette import ThemePalette
from haywire.ui.themes.base import ThemeMetadata
from haywire.ui.themes.utils import ColorUtils
from haywire.ui.themes.loader import ThemeValidationError

__all__ = [
    # Keys
    'ThemeKey',

    # Named color constants
    'Colors',
    
    # Theme management
    'ThemePalette',
    
    # Types and enums
    'ThemeMetadata',
    'ThemeKey',
    
    # Utilities
    'ColorUtils',
    
    # Exceptions
    'ThemeValidationError',
]
