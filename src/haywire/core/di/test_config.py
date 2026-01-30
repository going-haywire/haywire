# haywire/core/di/test_config.py
"""
Test-specific DI configuration for Haywire.

Provides lightweight configurations for different test scenarios.
"""

import tempfile
from pathlib import Path
from typing import Optional, List, TYPE_CHECKING
from injector import Injector

if TYPE_CHECKING:
    from .config import LibrarySystemService
    from ..settings import GlobalSettingsRegistry


def create_test_injector(
    project_root: Optional[str] = None,
    library_paths: Optional[List[str]] = None,
    enable_file_watching: bool = False,
    undo_config: Optional[object] = None,
    load_libraries: bool = False,
    settings_path: Optional[str] = None,
    watch_settings: bool = False,
    use_temp_settings: bool = True
) -> Injector:
    """
    Create a test-specific DI injector with minimal overhead.
    
    Args:
        project_root: Root path (auto-detected if None)
        library_paths: Additional library paths
        enable_file_watching: Disable for faster tests
        undo_config: Optional undo configuration
        load_libraries: Whether to load libraries (slow, integration only)
        settings_path: Path to settings TOML (default: temp file for isolation)
        watch_settings: Disable for faster tests
        use_temp_settings: If True and settings_path is None, use a temp file
                          to isolate tests from user settings
        
    Returns:
        Configured test injector
    """
    # Import here to avoid circular imports at module level
    from .config import HaywireModule
    
    # Use temp file for settings by default to isolate tests
    if settings_path is None and use_temp_settings:
        temp_dir = tempfile.mkdtemp(prefix='haywire_test_')
        settings_path = str(Path(temp_dir) / 'settings.toml')
    
    module = HaywireModule(
        project_root=project_root,
        library_paths=library_paths,
        enable_file_watching=enable_file_watching,
        undo_config=undo_config,
        default_theme='default',
        settings_path=settings_path,
        watch_settings=watch_settings
    )
    
    return Injector([module])


def create_test_library_system(
    project_root: Optional[str] = None,
    library_paths: Optional[List[str]] = None,
    load_libraries: bool = True,
    enable_file_watching: bool = False,
    settings_path: Optional[str] = None,
    watch_settings: bool = False,
    use_temp_settings: bool = True
) -> 'LibrarySystemService':
    """
    Create library system for integration tests.
    
    Args:
        project_root: Root path (auto-detected if None)
        library_paths: Additional library paths
        load_libraries: Whether to initialize libraries
        enable_file_watching: Usually False for tests
        settings_path: Path to settings TOML (default: temp file for isolation)
        watch_settings: Usually False for tests
        use_temp_settings: If True, use temp file to isolate from user settings
        
    Returns:
        LibrarySystemService (initialized if load_libraries=True)
    """
    # Import here to avoid circular imports
    from .config import LibrarySystemService
    
    injector = create_test_injector(
        project_root=project_root,
        library_paths=library_paths,
        enable_file_watching=enable_file_watching,
        load_libraries=load_libraries,
        settings_path=settings_path,
        watch_settings=watch_settings,
        use_temp_settings=use_temp_settings
    )
    
    service = LibrarySystemService(injector)
    
    if load_libraries:
        service.initialize()
    
    return service


def create_test_settings_registry(
    predefined_settings: Optional[dict] = None,
    register_builtins: bool = True
) -> 'GlobalSettingsRegistry':
    """
    Create an isolated settings registry for unit tests.
    
    This creates a registry without loading from any TOML file,
    useful for testing settings-dependent code in isolation.
    
    Args:
        predefined_settings: Optional dict of {name: value} to pre-set
        register_builtins: Whether to register built-in settings
        
    Returns:
        Isolated GlobalSettingsRegistry
        
    Example:
        registry = create_test_settings_registry({
            'ui.node.bg_color': '#ff0000',
            'debug.verbose_logging': True,
        })
    """
    from ..settings import GlobalSettingsRegistry, SettingMode
    from ..settings.builtins import register_all as register_builtin_settings
    
    registry = GlobalSettingsRegistry()
    
    if register_builtins:
        register_builtin_settings(registry)
    
    # Apply predefined settings
    if predefined_settings:
        for name, value in predefined_settings.items():
            if registry.has_definition(name):
                registry.set_global(name, value, SettingMode.SET)
            else:
                # Auto-define if not a builtin
                registry.define(name, value)
                registry.set_global(name, value, SettingMode.SET)
    
    return registry


def create_test_settings_holder(
    predefined_local: Optional[dict] = None,
    predefined_global: Optional[dict] = None,
    register_builtins: bool = True
) -> tuple['GlobalSettingsRegistry', 'SettingsHolder']:
    """
    Create an isolated settings registry and holder for unit tests.
    
    Useful for testing node settings behavior without full DI setup.
    
    Args:
        predefined_local: Optional dict of {name: value} for local settings
        predefined_global: Optional dict of {name: value} for global settings
        register_builtins: Whether to register built-in settings
        
    Returns:
        Tuple of (GlobalSettingsRegistry, SettingsHolder)
        
    Example:
        registry, holder = create_test_settings_holder(
            predefined_global={'ui.node.bg_color': '#ffffff'},
            predefined_local={'ui.node.bg_color': '#ff0000'}
        )
        
        # Local override wins
        assert holder['ui.node.bg_color'] == '#ff0000'
        
        # Check resolution info
        info = holder.get_info('ui.node.bg_color')
        assert info.source == 'local'
    """
    from ..settings import SettingsHolder, SettingMode
    
    registry = create_test_settings_registry(
        predefined_settings=predefined_global,
        register_builtins=register_builtins
    )
    
    holder = SettingsHolder(registry, owner=None, owner_name='test')
    
    # Apply predefined local settings
    if predefined_local:
        for name, value in predefined_local.items():
            holder.set(name, value, SettingMode.SET)
    
    return registry, holder


class SettingsTestContext:
    """
    Context manager for temporarily modifying settings in tests.
    
    Automatically restores original values after the test.
    
    Example:
        with SettingsTestContext(registry) as ctx:
            ctx.set('ui.node.bg_color', '#ff0000')
            ctx.set_override('ui.node.font_size', 16)
            
            # Test code here uses modified settings
            
        # Original settings restored automatically
    """
    
    def __init__(self, registry: 'GlobalSettingsRegistry'):
        self.registry = registry
        self._original_values: dict = {}
    
    def __enter__(self) -> 'SettingsTestContext':
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore original values
        from ..settings import SettingMode
        
        for name, original in self._original_values.items():
            if original is None:
                # Was not set before, reset to AUTO
                self.registry._global_values[name] = type(self.registry._global_values[name])()
            else:
                self.registry._global_values[name] = original
        
        return False
    
    def set(self, name: str, value: any) -> None:
        """Set a setting value (SET mode)."""
        from ..settings import SettingMode
        self._save_original(name)
        self.registry.set_global(name, value, SettingMode.SET)
    
    def set_override(self, name: str, value: any) -> None:
        """Set a setting value with OVERRIDE mode."""
        from ..settings import SettingMode
        self._save_original(name)
        self.registry.set_global(name, value, SettingMode.OVERRIDE)
    
    def reset(self, name: str) -> None:
        """Reset a setting to AUTO."""
        self._save_original(name)
        self.registry.reset_global(name)
    
    def _save_original(self, name: str) -> None:
        """Save original value if not already saved."""
        if name not in self._original_values:
            sv = self.registry._global_values.get(name)
            self._original_values[name] = type(sv)(mode=sv.mode, value=sv.value) if sv else None