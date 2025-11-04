"""
Named color constants for Haywire UI.

These are literal color name-to-value mappings only.
Semantic meanings (primary, error, etc.) belong in themes.
"""

from enum import Enum
from typing import Final


class Colors:
    """Hardcoded color name-to-value mappings with IDE preview support."""
    
    # Basic colors
    WHITE: Final[str] = "#ffffff"
    BLACK: Final[str] = "#000000"
    RED: Final[str] = "#ff0000"
    GREEN: Final[str] = "#00ff00"
    BLUE: Final[str] = "#0000ff"
    YELLOW: Final[str] = "#ffff00"
    CYAN: Final[str] = "#00ffff"
    MAGENTA: Final[str] = "#ff00ff"
    ORANGE: Final[str] = "#ff8800"
    PURPLE: Final[str] = "#800080"
    TRANSPARENT: Final[str] = "transparent"
    
    # Gray scale
    GRAY_50: Final[str] = "#fafafa"
    GRAY_100: Final[str] = "#f5f5f5"
    GRAY_200: Final[str] = "#eeeeee"
    GRAY_300: Final[str] = "#e0e0e0"
    GRAY_400: Final[str] = "#bdbdbd"
    GRAY_500: Final[str] = "#9e9e9e"
    GRAY_600: Final[str] = "#757575"
    GRAY_700: Final[str] = "#616161"
    GRAY_800: Final[str] = "#424242"
    GRAY_900: Final[str] = "#212121"
    
    @classmethod
    def get(cls, name: str, default: str = "#000000") -> str:
        """
        Get color by name with fallback.
        
        Args:
            name: Color name (case-insensitive)
            default: Fallback color if name not found
            
        Returns:
            Color value as hex string
        """
        # Convert name to uppercase
        normalized_name = name.upper()
        
        # Check if attribute exists
        if hasattr(cls, normalized_name):
            return getattr(cls, normalized_name)
        
        # Return default
        return default


class Theme_UI_Color(str, Enum):
    """UI theme color keys with IDE autocomplete support."""

    # Semantic colors
    PRIMARY = 'primary'
    SECONDARY = 'secondary'
    ACCENT = 'accent'

    # Status colors
    ERROR = 'error'
    WARNING = 'warning'
    SUCCESS = 'success'
    INFO = 'info'

    # Node/port specific
    NODE_BACKGROUND = 'node_background'
    NODE_BORDER = 'node_border'
    NODE_SELECTED_BORDER = 'node_selected_border'
    PORT_BORDER = 'port_border'
    PORT_DEFAULT = 'port_default'

    # Canvas
    CANVAS_BACKGROUND = 'canvas_background'
    CANVAS_GRID_LINE = 'canvas_grid_line'
    CANVAS_GRID_DOT = 'canvas_grid_dot'
    SELECTION_BOX = 'selection_box'
    SELECTION_BOX_BORDER = 'selection_box_border'

    # Text colors
    TEXT_PRIMARY = 'text_primary'
    TEXT_SECONDARY = 'text_secondary'
    TEXT_DISABLED = 'text_disabled'
    TEXT_HINT = 'text_hint'
