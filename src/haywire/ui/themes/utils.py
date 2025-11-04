"""
Color utility functions.
"""

import re
from typing import Optional, Tuple


class ColorUtils:
    """Utilities for color manipulation and validation."""
    
    # Regex patterns
    HEX_PATTERN = re.compile(r'^#[0-9a-fA-F]{6}$')
    HEX_SHORT_PATTERN = re.compile(r'^#[0-9a-fA-F]{3}$')
    RGBA_PATTERN = re.compile(
        r'^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+)\s*)?\)$'
    )
    
    @classmethod
    def is_valid_color(cls, color: str) -> bool:
        """
        Validate if string is a valid color.
        
        Args:
            color: Color string to validate
            
        Returns:
            True if valid color format, False otherwise
        """
        if not color or not isinstance(color, str):
            return False
            
        # Check if matches hex pattern (#RRGGBB or #RGB)
        if cls.HEX_PATTERN.match(color) or cls.HEX_SHORT_PATTERN.match(color):
            return True
        
        # Check if matches rgba pattern
        if cls.RGBA_PATTERN.match(color):
            return True
        
        # Check if equals 'transparent'
        if color.lower() == 'transparent':
            return True
        
        return False
    
    @classmethod
    def hex_to_rgba(cls, hex_color: str, alpha: float = 1.0) -> str:
        """
        Convert hex color to rgba format.
        
        Args:
            hex_color: Hex color string (#RRGGBB or #RGB)
            alpha: Alpha value (0.0 to 1.0)
        
        Returns:
            RGBA string: "rgba(r, g, b, alpha)"
        """
        # Validate hex_color format
        if not (cls.HEX_PATTERN.match(hex_color) or cls.HEX_SHORT_PATTERN.match(hex_color)):
            raise ValueError(f"Invalid hex color format: {hex_color}")
        
        # Handle short form (#RGB -> #RRGGBB)
        if len(hex_color) == 4:  # #RGB
            hex_color = f"#{hex_color[1]}{hex_color[1]}{hex_color[2]}{hex_color[2]}{hex_color[3]}{hex_color[3]}"
        
        # Extract R, G, B values
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
        
        # Clamp alpha between 0.0 and 1.0
        alpha = max(0.0, min(1.0, alpha))
        
        # Return formatted rgba string
        return f"rgba({r}, {g}, {b}, {alpha})"
    
    @classmethod
    def rgba_to_hex(cls, rgba_color: str) -> Optional[str]:
        """
        Convert rgba color to hex format (ignores alpha).
        
        Args:
            rgba_color: RGBA color string
            
        Returns:
            Hex color string or None if invalid
        """
        # Parse rgba string with regex
        match = cls.RGBA_PATTERN.match(rgba_color)
        if not match:
            return None
        
        # Extract R, G, B values
        r = int(match.group(1))
        g = int(match.group(2))
        b = int(match.group(3))
        
        # Clamp values to 0-255 range
        r = max(0, min(255, r))
        g = max(0, min(255, g))
        b = max(0, min(255, b))
        
        # Convert to hex format
        return f"#{r:02x}{g:02x}{b:02x}"
    
    @classmethod
    def parse_rgba(cls, rgba_color: str) -> Optional[Tuple[int, int, int, float]]:
        """
        Parse rgba string to component values.
        
        Args:
            rgba_color: RGBA color string
            
        Returns:
            Tuple of (r, g, b, alpha) or None if invalid
        """
        # Match against RGBA_PATTERN
        match = cls.RGBA_PATTERN.match(rgba_color)
        if not match:
            return None
        
        # Extract and convert values
        r = int(match.group(1))
        g = int(match.group(2))
        b = int(match.group(3))
        alpha = float(match.group(4)) if match.group(4) else 1.0
        
        # Clamp values
        r = max(0, min(255, r))
        g = max(0, min(255, g))
        b = max(0, min(255, b))
        alpha = max(0.0, min(1.0, alpha))
        
        return (r, g, b, alpha)
    
    @classmethod
    def adjust_alpha(cls, color: str, alpha: float) -> str:
        """
        Adjust alpha value of a color.
        
        Args:
            color: Hex or RGBA color string
            alpha: New alpha value (0.0 to 1.0)
            
        Returns:
            RGBA color string with adjusted alpha
        """
        # Clamp alpha
        alpha = max(0.0, min(1.0, alpha))
        
        # If hex, convert to rgba with new alpha
        if cls.HEX_PATTERN.match(color) or cls.HEX_SHORT_PATTERN.match(color):
            return cls.hex_to_rgba(color, alpha)
        
        # If rgba, parse and replace alpha
        parsed = cls.parse_rgba(color)
        if parsed:
            r, g, b, _ = parsed
            return f"rgba({r}, {g}, {b}, {alpha})"
        
        # If invalid, return as-is
        return color
    
    @classmethod
    def normalize_hex(cls, hex_color: str) -> str:
        """
        Normalize hex color to #RRGGBB format.
        
        Args:
            hex_color: Hex color string
            
        Returns:
            Normalized hex color string
        """
        # If #RGB format, expand to #RRGGBB
        if cls.HEX_SHORT_PATTERN.match(hex_color):
            return f"#{hex_color[1]}{hex_color[1]}{hex_color[2]}{hex_color[2]}{hex_color[3]}{hex_color[3]}"
        
        # Ensure uppercase
        if cls.HEX_PATTERN.match(hex_color):
            return hex_color.lower()
        
        # Return as-is if not a valid hex color
        return hex_color
