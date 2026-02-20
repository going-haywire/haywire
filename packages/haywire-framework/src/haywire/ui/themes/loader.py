"""
TOML theme file loader with validation and inheritance support.
"""

import tomllib
from pathlib import Path
from typing import Optional, List, Dict
from haywire.ui.themes.base import TOMLTheme
from haywire.ui.themes.utils import ColorUtils


class ThemeValidationError(Exception):
    """Raised when theme validation fails."""
    pass


class ThemeLoader:
    """
    Load and validate themes from TOML files.
    
    Features:
    - Define theme search paths (user dir, system dir)
    - Scan for .toml files
    - Parse and validate TOML structure
    - Create TOMLTheme instances with inheritance support
    - Cache loaded themes to avoid re-parsing
    """
    
    _loaded_themes_cache: Dict[str, TOMLTheme] = {}
    
    @classmethod
    def get_theme_directories(cls) -> List[Path]:
        """
        Get list of directories to search for themes.
        
        Returns:
            List of theme directory paths
        """
        directories = []
        
        # User directory: Path.home() / '.haywire' / 'themes'
        user_dir = Path.home() / '.haywire' / 'themes'
        
        # System directory: package data directory
        # Get the path to this file and navigate to data directory
        system_dir = Path(__file__).parent / 'data'
        
        # Create directories if they don't exist
        user_dir.mkdir(parents=True, exist_ok=True)
        system_dir.mkdir(parents=True, exist_ok=True)
        
        # Return list [user_dir, system_dir]
        directories.append(user_dir)
        directories.append(system_dir)
        
        return directories
    
    @classmethod
    def list_available_themes(cls) -> List[str]:
        """
        List all available TOML theme files.
        
        Returns:
            Sorted list of theme names
        """
        theme_names = set()
        
        # Iterate theme directories
        for directory in cls.get_theme_directories():
            # Find all .toml files
            for toml_file in directory.glob('*.toml'):
                # Extract theme name (filename without .toml)
                theme_name = toml_file.stem
                theme_names.add(theme_name)
        
        # Return sorted unique list
        return sorted(theme_names)
    
    @classmethod
    def load_theme(
        cls, 
        theme_name: str,
        theme_registry: Optional[Dict[str, any]] = None
    ) -> Optional[TOMLTheme]:
        """
        Load a theme by name with inheritance support.
        
        Args:
            theme_name: Name of theme to load
            theme_registry: Registry of available themes for inheritance resolution
        
        Returns:
            TOMLTheme instance or None if not found
        """
        # Check cache first
        if theme_name in cls._loaded_themes_cache:
            return cls._loaded_themes_cache[theme_name]
        
        # Search theme directories for {theme_name}.toml
        for directory in cls.get_theme_directories():
            theme_path = directory / f"{theme_name}.toml"
            
            if theme_path.exists():
                try:
                    # Load from path with registry
                    theme = cls._load_from_path(theme_path, theme_registry)
                    
                    # Cache result
                    cls._loaded_themes_cache[theme_name] = theme
                    
                    return theme
                except Exception as e:
                    print(f"Error loading theme '{theme_name}' from {theme_path}: {e}")
                    continue
        
        # Return None if not found
        return None
    
    @classmethod
    def _load_from_path(
        cls, 
        path: Path,
        theme_registry: Optional[Dict] = None
    ) -> TOMLTheme:
        """
        Load theme from TOML file path with inheritance.
        
        Args:
            path: Path to TOML file
            theme_registry: Registry of available themes for inheritance
            
        Returns:
            TOMLTheme instance
            
        Raises:
            ThemeValidationError: If validation fails
        """
        try:
            # Open file in binary mode
            with open(path, 'rb') as f:
                # Parse with tomllib.load()
                toml_data = tomllib.load(f)
            
            # Validate structure
            cls.validate_theme_data(toml_data, path)
            
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
                else:
                    # Try to load parent if not in registry
                    parent_theme = cls.load_theme(extends_name, theme_registry)
                    
                    if parent_theme is None:
                        print(
                            f"Warning: Parent theme '{extends_name}' "
                            f"not found for theme at {path}"
                        )
            
            # Create TOMLTheme with parent reference
            theme = TOMLTheme(toml_data, parent_theme)
            
            return theme
            
        except tomllib.TOMLDecodeError as e:
            raise ThemeValidationError(f"Failed to parse TOML file {path}: {e}")
        except Exception as e:
            raise ThemeValidationError(f"Error loading theme from {path}: {e}")
    
    @classmethod
    def validate_theme_data(cls, data: dict, path: Optional[Path] = None) -> None:
        """
        Validate TOML theme structure and color values.
        
        Args:
            data: Parsed TOML data
            path: Optional file path for error messages
            
        Raises:
            ThemeValidationError: If validation fails
        """
        path_str = f" in {path}" if path else ""
        
        # Check for metadata section
        if 'metadata' not in data:
            raise ThemeValidationError(f"Missing [metadata] section{path_str}")
        
        if 'name' not in data['metadata']:
            raise ThemeValidationError(f"Missing 'name' in [metadata] section{path_str}")
        
        # Check for at least one color section (data_types, flow_types, ui, canvas)
        color_sections = ['data_types', 'flow_types', 'ui', 'canvas']
        has_color_section = any(section in data for section in color_sections)
        
        if not has_color_section:
            raise ThemeValidationError(
                f"Theme must have at least one color section: "
                f"{', '.join(color_sections)}{path_str}"
            )
        
        # Verify each section is a dict and validate color values
        errors = []
        
        for section in color_sections:
            if section in data:
                if not isinstance(data[section], dict):
                    errors.append(f"Section [{section}] must be a dictionary")
                else:
                    # Validate each color value
                    section_errors = cls.validate_color_dict(data[section], section)
                    errors.extend(section_errors)
        
        # Raise ThemeValidationError with specific error messages
        if errors:
            error_msg = (
                f"Theme validation failed{path_str}:\n" + 
                "\n".join(f"  - {err}" for err in errors)
            )
            raise ThemeValidationError(error_msg)
    
    @classmethod
    def validate_color_dict(cls, color_dict: Dict[str, str], section_name: str) -> List[str]:
        """
        Validate colors in a dictionary section.
        
        Args:
            color_dict: Dictionary of color key-value pairs
            section_name: Name of the section (for error messages)
            
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        # Iterate over key-value pairs
        for key, value in color_dict.items():
            # Check if value is a string
            if not isinstance(value, str):
                errors.append(
                    f"[{section_name}] '{key}': value must be a string, "
                    f"got {type(value).__name__}"
                )
                continue
            
            # Check if valid using ColorUtils.is_valid_color()
            if not ColorUtils.is_valid_color(value):
                errors.append(f"[{section_name}] '{key}': invalid color format '{value}'")
        
        return errors
    
    @classmethod
    def clear_cache(cls) -> None:
        """
        Clear the theme cache.
        
        Useful for hot-reload scenarios.
        """
        cls._loaded_themes_cache.clear()
    
    @classmethod
    def reload_theme(
        cls,
        theme_name: str,
        theme_registry: Optional[Dict] = None
    ) -> Optional[TOMLTheme]:
        """
        Force reload a theme from disk, bypassing cache.
        
        Args:
            theme_name: Name of theme to reload
            theme_registry: Registry of available themes
            
        Returns:
            Reloaded theme instance or None
        """
        # Remove theme from cache if present
        if theme_name in cls._loaded_themes_cache:
            del cls._loaded_themes_cache[theme_name]
        
        # Call load_theme to reload from disk
        return cls.load_theme(theme_name, theme_registry)
