"""
Built-in theme implementations.
"""

from typing import Dict
from haywire.ui.themes.base import PythonTheme, ThemeMetadata
from haywire.ui.themes.keys import ThemeKey


class DefaultTheme(PythonTheme):
    """Default light theme."""
    
    metadata = ThemeMetadata(
        name="Default",
        author="Haywire Team",
        description="Default light color scheme",
        priority="Preference"
    )
    
    # Unified VALUES dict with all theme keys
    VALUES = {
        ThemeKey.UI_PORT_ICON_IN_MULTI_SINGLE: "fiber_smart_record",
        ThemeKey.UI_PORT_ICON_IN_MULTI_COMPOUND: "web_stories",
        ThemeKey.UI_PORT_ICON_IN_COMPOUND: "view_day",
        ThemeKey.UI_PORT_ICON_IN_SINGLE: "my_location",
        ThemeKey.UI_PORT_ICON_OUT_MULTI_COMPOUND: "view_day",
        ThemeKey.UI_PORT_ICON_OUT_MULTI_SINGLE: "circle",
        ThemeKey.UI_PORT_ICON_OUT_COMPOUND: "view_day",
        ThemeKey.UI_PORT_ICON_OUT_SINGLE: "circle",

        # UI - Semantic colors
        ThemeKey.UI_PRIMARY: "#2196f3",
        ThemeKey.UI_SECONDARY: "#757575",
        ThemeKey.UI_ACCENT: "#ff4081",
        
        # UI - Status colors
        ThemeKey.UI_ERROR: "#f44336",
        ThemeKey.UI_WARNING: "#ff9800",
        ThemeKey.UI_SUCCESS: "#4caf50",
        ThemeKey.UI_INFO: "#2196f3",
        
        # UI - Node/Port
        ThemeKey.UI_NODE_BACKGROUND: "rgba(255, 255, 255, 0.3)",
        ThemeKey.UI_NODE_BORDER: "#ffffff",
        ThemeKey.UI_NODE_SELECTED_BORDER: "#2196f3",
        ThemeKey.UI_PORT_BORDER: "#ffffff",
        ThemeKey.UI_PORT_DEFAULT: "#757575",
        
        # UI - Canvas
        ThemeKey.UI_CANVAS_BACKGROUND: "#1e1e1e",
        ThemeKey.UI_CANVAS_GRID_LINE: "#2d2d2d",
        ThemeKey.UI_CANVAS_GRID_DOT: "#404040",
        ThemeKey.UI_SELECTION_BOX: "rgba(33, 150, 243, 0.3)",
        ThemeKey.UI_SELECTION_BOX_BORDER: "#2196f3",
        
        # UI - Text
        ThemeKey.UI_TEXT_PRIMARY: "#212121",
        ThemeKey.UI_TEXT_SECONDARY: "#757575",
        ThemeKey.UI_TEXT_DISABLED: "#bdbdbd",
        ThemeKey.UI_TEXT_HINT: "#9e9e9e",
    }


class DarkTheme(PythonTheme):
    """Dark theme optimized for low-light environments."""
    
    metadata = ThemeMetadata(
        name="Dark",
        author="Haywire Team",
        description="Dark color scheme for low-light environments",
        extends="default",
        priority="Preference"
    )
    
    # Only override the colors that differ from DefaultTheme
    VALUES = {
        # UI - Node/Port
        ThemeKey.UI_NODE_BACKGROUND: "rgba(30, 30, 30, 0.9)",
        ThemeKey.UI_NODE_BORDER: "#424242",
        ThemeKey.UI_NODE_SELECTED_BORDER: "#42a5f5",
        ThemeKey.UI_PORT_BORDER: "#616161",
        ThemeKey.UI_PORT_DEFAULT: "#9e9e9e",
        
        # UI - Text
        ThemeKey.UI_TEXT_PRIMARY: "#ffffff",
        ThemeKey.UI_TEXT_SECONDARY: "#b0b0b0",
        ThemeKey.UI_TEXT_DISABLED: "#616161",
        ThemeKey.UI_TEXT_HINT: "#757575",
    }


# Registry of built-in themes
BUILTIN_THEMES: Dict[str, type[PythonTheme]] = {
    'default': DefaultTheme,
    'dark': DarkTheme,
}

