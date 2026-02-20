"""
Named color constants and unified theme keys for Haywire.
"""

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


