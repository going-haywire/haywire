"""
Base classes and protocols for theme system.
"""

from typing import Dict, Optional, Callable
from dataclasses import dataclass


@dataclass
class ThemeMetadata:
    """Theme metadata information."""
    name: str
    author: str = ""
    description: str = ""
    version: str = "1.0.0"
    extends: Optional[str] = None  # Base theme to inherit from
    priority: str = "Preference"  # 'Theme' or 'Preference'


class BaseTheme:
    """
    Base class for theme implementations.
    
    Provides unified get() method for all theme values.
    Supports metadata and inheritance from parent theme.
    """
    
    def __init__(
        self, 
        metadata: ThemeMetadata,
        parent_theme: Optional['BaseTheme'] = None
    ):
        """
        Initialize with metadata and optional parent theme.
        
        Args:
            metadata: Theme metadata
            parent_theme: Optional parent theme for inheritance
        """
        self.metadata = metadata
        self._parent_theme = parent_theme
        
        # Initialize unified values dict
        self._values: Dict[str, str] = {}
    
    def set_parent_theme(self, parent: 'BaseTheme') -> None:
        """Set parent theme for inheritance."""
        self._parent_theme = parent
    
    def get(
        self, 
        key: str, 
        preference: Optional[str] = None, 
        fallback: Optional[str] = None
    ) -> str:
        """
        Get theme value with priority-based preference handling.
        
        Priority logic:
        - If preference is None:
          - Return theme value (or parent's value)
          - If not found, return fallback or ''
        
        - If preference is provided:
          - Priority='Theme': Return theme value, else preference, else fallback, else ''
          - Priority='Preference' (default): Return preference (ignore theme)
        
        Args:
            key: Theme key (any string)
            preference: User preference value (optional)
            fallback: Fallback value if key not found (optional)
        
        Returns:
            Theme value as string, or '' if not found
        """
        # Normalize key to lowercase for case-insensitive lookup
        normalized_key = key.lower()
        
        # Get theme value (check this theme first, then parent)
        theme_value = self._get_theme_value(normalized_key)
        
        # If preference is None, use theme value or fallback
        if preference is None:
            if theme_value is not None:
                return theme_value
            return fallback if fallback is not None else ''
        
        # Preference is provided - check priority
        if self.metadata.priority == 'Theme':
            # Theme has priority
            if theme_value is not None:
                return theme_value
            # Theme doesn't have this key, use preference
            return preference
        else:
            # Preference has priority (default behavior)
            return preference
    
    def _get_theme_value(self, normalized_key: str) -> Optional[str]:
        """
        Get value from this theme or parent theme.
        
        Args:
            normalized_key: Normalized key to look up
        
        Returns:
            Value if found, None otherwise
        """
        # Check this theme's values
        if normalized_key in self._values:
            return self._values[normalized_key]
        
        # Check parent theme
        if self._parent_theme is not None:
            parent_value = self._parent_theme._get_theme_value(normalized_key)
            if parent_value is not None:
                return parent_value
        
        return None


class PythonTheme(BaseTheme):
    """
    Theme defined in Python with class attributes.
    
    Supports Final[str] for IDE preview and uses class attribute
    for unified theme values.
    """
    
    # Class attribute to be overridden in subclasses
    VALUES: Dict[str, str] = {}
    
    # Metadata as class attribute
    metadata: ThemeMetadata = ThemeMetadata(name="Base Python Theme")
    
    def __init__(self, parent_theme: Optional[BaseTheme] = None):
        """
        Initialize from class attributes.
        
        Args:
            parent_theme: Optional parent theme for inheritance
        """
        # Create metadata from class metadata attribute
        super().__init__(self.metadata, parent_theme)
        
        # Copy class attribute to instance dict (normalize keys to lowercase)
        self._values = {k.lower(): v for k, v in self.VALUES.items()}



class TOMLTheme(BaseTheme):
    """
    Theme loaded from TOML file.
    
    Accepts parsed TOML data and extracts values and metadata.
    """
    
    def __init__(self, toml_data: Dict, parent_theme: Optional[BaseTheme] = None):
        """
        Initialize from TOML data.
        
        Args:
            toml_data: Parsed TOML data dictionary
            parent_theme: Optional parent theme for inheritance
        """
        # Extract metadata section
        metadata_dict = toml_data.get('metadata', {})
        metadata = ThemeMetadata(
            name=metadata_dict.get('name', 'Unnamed Theme'),
            author=metadata_dict.get('author', ''),
            description=metadata_dict.get('description', ''),
            version=metadata_dict.get('version', '1.0.0'),
            extends=metadata_dict.get('extends'),
            priority=metadata_dict.get('priority', 'Preference')
        )
        
        # Call super().__init__()
        super().__init__(metadata, parent_theme)
        
        # Extract and populate all values sections (normalize keys to lowercase)
        # Support multiple sections for organization but store in unified dict
        for section_name, section_data in toml_data.items():
            if section_name != 'metadata' and isinstance(section_data, dict):
                # Add section prefix to keys for namespacing
                for key, value in section_data.items():
                    # Store as "section.key" (already normalized in ThemeKey)
                    full_key = f"{section_name}.{key}".lower()
                    self._values[full_key] = value
            
    @classmethod
    def from_file(cls, path: str, theme_registry: Optional[Dict] = None) -> 'TOMLTheme':
        """
        Create theme from TOML file with inheritance support.
        
        Args:
            path: Path to TOML file
            theme_registry: Registry of available themes for inheritance resolution
            
        Returns:
            TOMLTheme instance
        """
        import tomllib
        from pathlib import Path
        
        # Parse TOML file
        file_path = Path(path)
        with open(file_path, 'rb') as f:
            toml_data = tomllib.load(f)
        
        # Check for 'extends' in metadata
        parent_theme = None
        if 'metadata' in toml_data and 'extends' in toml_data['metadata']:
            extends_name = toml_data['metadata']['extends']
            
            # Resolve parent theme from registry
            if theme_registry and extends_name in theme_registry:
                parent_ref = theme_registry[extends_name]
                # If it's a class, instantiate it
                if isinstance(parent_ref, type):
                    parent_theme = parent_ref()
                else:
                    parent_theme = parent_ref
        
        # Create TOMLTheme with parent
        return cls(toml_data, parent_theme)
