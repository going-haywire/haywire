"""
Base classes and protocols for theme system.
"""

from typing import Protocol, Dict, Optional, Callable, Any
from dataclasses import dataclass, field


@dataclass
class ThemeMetadata:
    """Theme metadata information."""
    name: str
    author: str = ""
    description: str = ""
    version: str = "1.0.0"
    extends: Optional[str] = None  # Base theme to inherit from


class BaseTheme:
    """
    Base class for theme implementations.
    
    Provides color dictionaries for each category and get methods with fallbacks.
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
        
        # Initialize empty color dicts
        self._data_types: Dict[str, str] = {}
        self._flow_types: Dict[str, str] = {}
        self._ui_colors: Dict[str, str] = {}
    
    def set_parent_theme(self, parent: 'BaseTheme') -> None:
        """Set parent theme for inheritance."""
        self._parent_theme = parent
    
    def get_data_type_color(self, data_type: str, default: Optional[str] = None) -> str:
        """
        Get color for data type with inheritance support.
        
        Args:
            data_type: Data type name
            default: Fallback color
            
        Returns:
            Color value
        """
        # Normalize data_type to lowercase
        normalized_key = data_type.lower()
        
        # Use inheritance-aware getter
        return self._get_with_inheritance(
            self._data_types,
            normalized_key,
            default or self.get_ui_color('port_default', '#757575'),
            lambda k, d: self._parent_theme.get_data_type_color(k, d) if self._parent_theme else d
        )
    
    def get_flow_type_color(self, flow_type: str, default: Optional[str] = None) -> str:
        """
        Get color for flow type with inheritance support.
        
        Args:
            flow_type: Flow type name
            default: Fallback color
            
        Returns:
            Color value
        """
        # Normalize flow_type to lowercase
        normalized_key = flow_type.lower()
        
        return self._get_with_inheritance(
            self._flow_types,
            normalized_key,
            default or '#757575',
            lambda k, d: self._parent_theme.get_flow_type_color(k, d) if self._parent_theme else d
        )
    
    def get_ui_color(self, element: str, default: Optional[str] = None) -> str:
        """
        Get color for UI element with inheritance support.
        
        Args:
            element: UI element name
            default: Fallback color
            
        Returns:
            Color value
        """
        normalized_key = element.lower()
        
        return self._get_with_inheritance(
            self._ui_colors,
            normalized_key,
            default or '#757575',
            lambda k, d: self._parent_theme.get_ui_color(k, d) if self._parent_theme else d
        )
        
    def _get_with_inheritance(
        self,
        color_dict: Dict[str, str],
        key: str,
        default: Optional[str],
        getter_method: Callable[[str, Optional[str]], str]
    ) -> str:
        """
        Internal helper for inheritance-aware color lookup.
        
        Args:
            color_dict: Local color dictionary
            key: Color key to look up
            default: Default value if not found
            getter_method: Method to call on parent theme
            
        Returns:
            Color value
        """
        # Check local color_dict
        if key in color_dict:
            return color_dict[key]
        
        # If not found and parent exists, call getter_method on parent
        if self._parent_theme:
            return getter_method(key, default)
        
        # If still not found, return default
        return default or '#000000'


class PythonTheme(BaseTheme):
    """
    Theme defined in Python with class attributes.
    
    Supports Final[str] for IDE preview and uses class attributes
    for color dictionaries.
    """
    
    # Class attributes (to be overridden in subclasses)
    DATA_TYPES: Dict[str, str] = {}
    FLOW_TYPES: Dict[str, str] = {}
    UI_COLORS: Dict[str, str] = {}
    CANVAS_COLORS: Dict[str, str] = {}  # Deprecated: kept for backward compatibility
    
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
        
        # Copy class attributes to instance dicts (convert keys to lowercase)
        self._data_types = {k.lower(): v for k, v in self.DATA_TYPES.items()}
        self._flow_types = {k.lower(): v for k, v in self.FLOW_TYPES.items()}
        self._ui_colors = {k.lower(): v for k, v in self.UI_COLORS.items()}



class TOMLTheme(BaseTheme):
    """
    Theme loaded from TOML file.
    
    Accepts parsed TOML data and extracts sections for colors and metadata.
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
            extends=metadata_dict.get('extends')
        )
        
        # Call super().__init__()
        super().__init__(metadata, parent_theme)
        
        # Extract and populate color sections (normalize keys to lowercase)
        if 'data_types' in toml_data:
            self._data_types = {k.lower(): v for k, v in toml_data['data_types'].items()}
        
        if 'flow_types' in toml_data:
            self._flow_types = {k.lower(): v for k, v in toml_data['flow_types'].items()}
        
        if 'ui' in toml_data:
            self._ui_colors = {k.lower(): v for k, v in toml_data['ui'].items()}
            
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
