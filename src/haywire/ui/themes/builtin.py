"""
Built-in theme implementations.
"""

from typing import Dict
from haywire.ui.themes.base import PythonTheme, ThemeMetadata
from haywire.ui.themes.colors import Theme_UI_Color
from haywire.core.data.enums import FlowType


class DefaultTheme(PythonTheme):
    """Default light theme."""
    
    metadata = ThemeMetadata(
        name="Default",
        author="Haywire Team",
        description="Default light color scheme"
    )
    
    # Data type colors - using Python type name strings
    DATA_TYPES = {
        'float': "#50b0ff",
        'int': "#f7b0ff",
        'str': "#4caf50",
        'bool': "#ff9800",
        'list': "#9c27b0",
        'dict': "#795548",
        'bytes': "#9e9e9e",
        'any': "#bababa",  # Default for unknown/custom types
    }
    
    # Flow type colors - using FlowType enum keys
    FLOW_TYPES = {
        FlowType.CTRL.value: "#0000ff",
        FlowType.CALLBACK.value: "#ff0000",
        FlowType.DATA.value: "#00ff00",
    }
    
    # UI colors - using UIThemeColor enum keys (includes canvas colors)
    UI_COLORS = {
        # Semantic colors
        Theme_UI_Color.PRIMARY.value: "#2196f3",
        Theme_UI_Color.SECONDARY.value: "#757575",
        Theme_UI_Color.ACCENT.value: "#ff4081",
        
        # Status colors
        Theme_UI_Color.ERROR.value: "#f44336",
        Theme_UI_Color.WARNING.value: "#ff9800",
        Theme_UI_Color.SUCCESS.value: "#4caf50",
        Theme_UI_Color.INFO.value: "#2196f3",
        
        # Node/port specific
        Theme_UI_Color.NODE_BACKGROUND.value: "rgba(255, 255, 255, 0.3)",
        Theme_UI_Color.NODE_BORDER.value: "#ffffff",
        Theme_UI_Color.NODE_SELECTED_BORDER.value: "#2196f3",
        Theme_UI_Color.PORT_BORDER.value: "#ffffff",
        Theme_UI_Color.PORT_DEFAULT.value: "#757575",
        
        # Canvas colors (merged into UI_COLORS)
        Theme_UI_Color.CANVAS_BACKGROUND.value: "#1e1e1e",
        Theme_UI_Color.CANVAS_GRID_LINE.value: "#2d2d2d",
        Theme_UI_Color.CANVAS_GRID_DOT.value: "#404040",
        Theme_UI_Color.SELECTION_BOX.value: "rgba(33, 150, 243, 0.3)",
        Theme_UI_Color.SELECTION_BOX_BORDER.value: "#2196f3",
        
        # Text colors
        Theme_UI_Color.TEXT_PRIMARY.value: "#212121",
        Theme_UI_Color.TEXT_SECONDARY.value: "#757575",
        Theme_UI_Color.TEXT_DISABLED.value: "#bdbdbd",
        Theme_UI_Color.TEXT_HINT.value: "#9e9e9e",
    }


class DarkTheme(DefaultTheme):
    """Dark theme optimized for low-light environments."""
    
    metadata = ThemeMetadata(
        name="Dark",
        author="Haywire Team",
        description="Dark color scheme for low-light environments"
    )
    
    # Only override the colors that differ from DefaultTheme
    # All other colors are inherited automatically
    UI_COLORS = {
        **DefaultTheme.UI_COLORS,  # Inherit all default colors
        # Override only what we want to change - using UIThemeColor enum:
        
        # Node/port specific
        Theme_UI_Color.NODE_BACKGROUND.value: "rgba(30, 30, 30, 0.9)",
        Theme_UI_Color.NODE_BORDER.value: "#424242",
        Theme_UI_Color.NODE_SELECTED_BORDER.value: "#42a5f5",
        Theme_UI_Color.PORT_BORDER.value: "#616161",
        Theme_UI_Color.PORT_DEFAULT.value: "#9e9e9e",
        
        # Text colors
        Theme_UI_Color.TEXT_PRIMARY.value: "#ffffff",
        Theme_UI_Color.TEXT_SECONDARY.value: "#b0b0b0",
        Theme_UI_Color.TEXT_DISABLED.value: "#616161",
        Theme_UI_Color.TEXT_HINT.value: "#757575",
    }


# Registry of built-in themes
BUILTIN_THEMES: Dict[str, type[PythonTheme]] = {
    'default': DefaultTheme,
    'dark': DarkTheme,
}

