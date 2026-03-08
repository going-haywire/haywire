"""
Theme palette manager — thin shim kept for transition.

New code should use ThemeRegistry + WorkbenchTheme (via DI).
ThemePalette still works for legacy callers that read individual theme keys.
"""

from typing import Optional, Callable, List, Dict, Any
from haywire.ui.themes.base import BaseTheme
from haywire.ui.themes.builtin import BUILTIN_THEMES, DefaultTheme
from haywire.ui.themes.loader import ThemeLoader


# Type alias for observer callbacks
ThemeChangeObserver = Callable[[str, BaseTheme], None]


class ThemePalette:
    """
    Central theme manager with observer pattern.
    
    Provides:
    - Theme switching
    - Color access methods
    - Observer registration for hot-reload
    - Theme registry for inheritance resolution
    """
    
    _current_theme: BaseTheme = DefaultTheme()
    _current_theme_key: str = "default"  # Track the theme key/file name
    _theme_cache: Dict[str, BaseTheme] = {}
    _observers: List[ThemeChangeObserver] = []
    
    @classmethod
    def set_theme(cls, theme_name: str) -> bool:
        """
        Set active theme by name and notify observers.
        
        Args:
            theme_name: Name of theme to activate
        
        Returns:
            True if theme was set successfully, False otherwise
        """
        try:
            # Build theme registry (built-in + cached + loadable)
            registry = cls._build_theme_registry()
            
            # Check if theme_name in BUILTIN_THEMES
            if theme_name in BUILTIN_THEMES:
                # Instantiate with inheritance support
                theme_class = BUILTIN_THEMES[theme_name]
                theme_instance = theme_class()
                
                # Cache and set as _current_theme
                cls._theme_cache[theme_name] = theme_instance
                cls._current_theme = theme_instance
                cls._current_theme_key = theme_name  # Store the key
                
                # Call _notify_observers()
                cls._notify_observers()
                return True
            
            # Try to load from TOML via ThemeLoader with registry
            toml_theme = ThemeLoader.load_theme(theme_name, registry)
            
            if toml_theme:
                # Cache and set as _current_theme
                cls._theme_cache[theme_name] = toml_theme
                cls._current_theme = toml_theme
                cls._current_theme_key = theme_name  # Store the key
                
                # Call _notify_observers()
                cls._notify_observers()
                return True
            
            # Theme not found
            print(f"Theme '{theme_name}' not found")
            return False
            
        except Exception as e:
            print(f"Error setting theme '{theme_name}': {e}")
            return False
    
    @classmethod
    def get_current_theme(cls) -> BaseTheme:
        """Get the currently active theme."""
        return cls._current_theme
    
    @classmethod
    def get_theme_name(cls) -> str:
        """Get name of current theme."""
        return cls._current_theme.metadata.name
    
    @classmethod
    def get_theme_key(cls) -> str:
        """Get the key/file name of current theme."""
        return cls._current_theme_key
    
    @classmethod
    def list_themes(cls) -> List[str]:
        """
        List all available themes (built-in + TOML).
        
        Returns:
            Sorted list of theme names
        """
        # Get built-in theme names from BUILTIN_THEMES
        builtin_names = list(BUILTIN_THEMES.keys())
        
        # Get TOML theme names from ThemeLoader
        toml_names = ThemeLoader.list_available_themes()
        
        # Combine and return sorted unique list
        all_themes = set(builtin_names + toml_names)
        return sorted(all_themes)
    
    @classmethod
    def register_observer(cls, observer: ThemeChangeObserver) -> None:
        """
        Register an observer for theme changes.
        
        Args:
            observer: Callback function(theme_name: str, theme: BaseTheme)
        """
        if observer not in cls._observers:
            cls._observers.append(observer)
    
    @classmethod
    def unregister_observer(cls, observer: ThemeChangeObserver) -> None:
        """
        Unregister an observer.
        
        Args:
            observer: Observer to remove
        """
        if observer in cls._observers:
            cls._observers.remove(observer)
    
    @classmethod
    def _notify_observers(cls) -> None:
        """
        Notify all observers of theme change.
        """
        # Get current theme name and object
        theme_name = cls.get_theme_name()
        theme_object = cls._current_theme
        
        # For each observer in _observers
        for observer in cls._observers:
            try:
                # Call observer(theme_name, theme_object)
                observer(theme_name, theme_object)
            except Exception as e:
                # Catch and log exceptions to prevent observer errors from breaking system
                print(f"Error in theme change observer: {e}")
    
    @classmethod
    def reload_current_theme(cls) -> bool:
        """
        Reload the current theme from disk (useful for TOML themes).
        
        Returns:
            True if reload successful, False otherwise
        """
        # Get current theme name
        theme_name = cls.get_theme_name()
        
        # Check if current theme is a TOML theme (not in BUILTIN_THEMES)
        if theme_name.lower() not in [name.lower() for name in BUILTIN_THEMES.keys()]:
            try:
                # Clear from cache
                if theme_name in cls._theme_cache:
                    del cls._theme_cache[theme_name]
                
                # Reload via ThemeLoader
                registry = cls._build_theme_registry()
                reloaded_theme = ThemeLoader.reload_theme(theme_name, registry)
                
                if reloaded_theme:
                    # Set as current theme
                    cls._theme_cache[theme_name] = reloaded_theme
                    cls._current_theme = reloaded_theme
                    
                    # Notify observers
                    cls._notify_observers()
                    return True
                
                return False
            except Exception as e:
                print(f"Error reloading theme '{theme_name}': {e}")
                return False
        else:
            # Built-in theme, just re-instantiate
            return cls.set_theme(theme_name)
    
    @classmethod
    def clear_cache(cls) -> None:
        """
        Clear theme cache.
        """
        cls._theme_cache.clear()
        ThemeLoader.clear_cache()
    
    @classmethod
    def _build_theme_registry(cls) -> Dict[str, Any]:
        """
        Build complete theme registry for inheritance resolution.
        
        Returns:
            Dict mapping theme names to theme classes/instances
        """
        # Start with BUILTIN_THEMES
        registry = dict(BUILTIN_THEMES)
        
        # Add cached themes
        registry.update(cls._theme_cache)
        
        return registry
    
    # Main access method - delegates to current theme
    
    @classmethod
    def get(
        cls,
        key: str,
        preference: Optional[str] = None,
        fallback: Optional[str] = None
    ) -> str:
        """
        Get theme value with preference and fallback support.
        
        Args:
            key: Theme key (any string, e.g., ThemeKey enum value or custom key)
            preference: User preference value (optional)
            fallback: Fallback value if key not found (optional)
        
        Returns:
            Theme value as string, or '' if not found
        """
        return cls._current_theme.get(key, preference, fallback)
