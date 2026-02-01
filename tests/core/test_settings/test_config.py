# haywire/core/di/test_config.py
"""
Test-specific DI configuration for Haywire.

Provides lightweight configurations for different test scenarios.
"""

import tempfile
from pathlib import Path
from typing import Optional, List, Any, TYPE_CHECKING
from injector import Injector

from haywire.core.di.config import LibrarySystemService
from haywire.core.settings import GlobalSettingsRegistry, SettingsHolder, SettingMode, SettingValue
from haywire.core.settings.builtins import register_all as register_builtin_settings


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
        enable_file_watching: Disable for faster tests (default: False)
        undo_config: Optional undo configuration
        load_libraries: Whether to load libraries (slow, integration only)
        settings_path: Path to settings TOML (default: temp file for isolation)
        watch_settings: Disable for faster tests (default: False)
        use_temp_settings: If True and settings_path is None, use a temp file
                          to isolate tests from user settings (default: True)
        
    Returns:
        Configured test injector
    """
    from haywire.core.di.config import HaywireModule
    
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
        load_libraries: Whether to initialize libraries (default: True)
        enable_file_watching: Usually False for tests
        settings_path: Path to settings TOML (default: temp file for isolation)
        watch_settings: Usually False for tests
        use_temp_settings: If True, use temp file to isolate from user settings
        
    Returns:
        LibrarySystemService (initialized if load_libraries=True)
    """
    from haywire.core.di.config import LibrarySystemService
    
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
    predefined_settings: Optional[dict[str, Any]] = None,
    register_builtins: bool = True
) -> 'GlobalSettingsRegistry':
    """
    Create an isolated settings registry for unit tests.
    
    This creates a registry without loading from any TOML file,
    useful for testing settings-dependent code in isolation.
    
    Args:
        predefined_settings: Optional dict of {name: value} to pre-set
        register_builtins: Whether to register built-in settings (default: True)
        
    Returns:
        Isolated GlobalSettingsRegistry
        
    Example:
        >>> registry = create_test_settings_registry({
        ...     'ui.node.bg_color': '#ff0000',
        ...     'debug.verbose_logging': True,
        ... })
        >>> value, source = registry.resolve('ui.node.bg_color')
        >>> assert value == '#ff0000'
    """
    
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
    predefined_local: Optional[dict[str, Any]] = None,
    predefined_global: Optional[dict[str, Any]] = None,
    register_builtins: bool = True
) -> tuple['GlobalSettingsRegistry', 'SettingsHolder']:
    """
    Create an isolated settings registry and holder for unit tests.
    
    Useful for testing node settings behavior without full DI setup.
    
    Args:
        predefined_local: Optional dict of {name: value} for local settings
        predefined_global: Optional dict of {name: value} for global settings
        register_builtins: Whether to register built-in settings (default: True)
        
    Returns:
        Tuple of (GlobalSettingsRegistry, SettingsHolder)
        
    Example:
        >>> registry, holder = create_test_settings_holder(
        ...     predefined_global={'ui.node.bg_color': '#ffffff'},
        ...     predefined_local={'ui.node.bg_color': '#ff0000'}
        ... )
        >>> # Local override wins
        >>> assert holder['ui.node.bg_color'] == '#ff0000'
        >>> # Check resolution info
        >>> info = holder.get_info('ui.node.bg_color')
        >>> assert info.source == 'local'
    """
    
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
    
    Automatically restores original values after the test, even if
    the test raises an exception.
    
    Example:
        >>> service = create_test_library_system(load_libraries=False)
        >>> registry = service.get_settings_registry()
        >>> 
        >>> with SettingsTestContext(registry) as ctx:
        ...     ctx.set('debug.verbose_logging', True)
        ...     ctx.set_override('ui.node.font_size', 20)
        ...     
        ...     # Test code here uses modified settings
        ...     assert registry.resolve('debug.verbose_logging')[0] == True
        ...
        >>> # Original settings restored automatically
        >>> assert registry.resolve('debug.verbose_logging')[0] == False
    """
    
    def __init__(self, registry: 'GlobalSettingsRegistry'):
        """
        Initialize context with registry.
        
        Args:
            registry: The settings registry to modify
        """
        
        self.registry = registry
        self._original_values: dict[str, SettingValue] = {}
    
    def __enter__(self) -> 'SettingsTestContext':
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore original values        
        for name, original in self._original_values.items():
            if original is None:
                # Was AUTO before, reset to AUTO
                self.registry._global_values[name] = SettingValue(mode=SettingMode.AUTO)
            else:
                self.registry._global_values[name] = original
        
        return False  # Don't suppress exceptions
    
    def set(self, name: str, value: Any) -> 'SettingsTestContext':
        """
        Set a setting value (SET mode).
        
        Args:
            name: Setting name
            value: Value to set
            
        Returns:
            Self for chaining
        """
        self._save_original(name)
        self.registry.set_global(name, value, SettingMode.SET)
        return self
    
    def set_override(self, name: str, value: Any) -> 'SettingsTestContext':
        """
        Set a setting value with OVERRIDE mode.
        
        Args:
            name: Setting name
            value: Value to set
            
        Returns:
            Self for chaining
        """
        self._save_original(name)
        self.registry.set_global(name, value, SettingMode.OVERRIDE)
        return self
    
    def reset(self, name: str) -> 'SettingsTestContext':
        """
        Reset a setting to AUTO (default/inherited).
        
        Args:
            name: Setting name
            
        Returns:
            Self for chaining
        """
        self._save_original(name)
        self.registry.reset_global(name)
        return self
    
    def _save_original(self, name: str) -> None:
        """Save original value if not already saved."""
        
        name = name.lower()
        if name not in self._original_values:
            sv = self.registry._global_values.get(name)
            if sv:
                # Deep copy the original
                self._original_values[name] = SettingValue(
                    mode=sv.mode, 
                    value=sv.value
                )
            else:
                self._original_values[name] = None


class MockExecutionContext:
    """
    Mock execution context for testing nodes.
    
    Provides a simple implementation of the execution context interface
    for use in unit tests.
    
    Example:
        >>> ctx = MockExecutionContext()
        >>> ctx.log("Processing...")
        >>> ctx.log("Done!")
        >>> assert len(ctx.logs) == 2
        >>> assert "Processing" in ctx.logs[0]
    """
    
    def __init__(self):
        """Initialize with empty logs and data."""
        self.logs: list[str] = []
        self.warnings: list[str] = []
        self.errors: list[str] = []
        self.data: dict[str, Any] = {}
        self.progress: float = 0.0
        self.cancelled: bool = False
    
    def log(self, message: str) -> None:
        """Log an info message."""
        self.logs.append(message)
    
    def warn(self, message: str) -> None:
        """Log a warning message."""
        self.warnings.append(message)
    
    def error(self, message: str) -> None:
        """Log an error message."""
        self.errors.append(message)
    
    def debug(self, message: str) -> None:
        """Log a debug message (added to logs)."""
        self.logs.append(f"[DEBUG] {message}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get context data."""
        return self.data.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set context data."""
        self.data[key] = value
    
    def set_progress(self, progress: float) -> None:
        """Set execution progress (0.0 to 1.0)."""
        self.progress = max(0.0, min(1.0, progress))
    
    def is_cancelled(self) -> bool:
        """Check if execution was cancelled."""
        return self.cancelled
    
    def cancel(self) -> None:
        """Mark execution as cancelled."""
        self.cancelled = True
    
    def clear(self) -> None:
        """Clear all logs, data, and reset state."""
        self.logs.clear()
        self.warnings.clear()
        self.errors.clear()
        self.data.clear()
        self.progress = 0.0
        self.cancelled = False
    
    def all_messages(self) -> list[str]:
        """Get all messages (logs, warnings, errors) in order."""
        return self.logs + self.warnings + self.errors


# =============================================================================
# Example Tests (can be run with pytest)
# =============================================================================

def test_node_uses_setting():
    """Test that settings can be accessed from registry."""
    registry = create_test_settings_registry({
        'ui.node.bg_color': '#ff0000'
    })
    
    value, source = registry.resolve('ui.node.bg_color')
    assert value == '#ff0000'
    assert source == 'global'


def test_local_overrides_global():
    """Test that local values override global."""
    registry, holder = create_test_settings_holder(
        predefined_global={'ui.node.bg_color': '#ffffff'},
        predefined_local={'ui.node.bg_color': '#ff0000'}
    )
    
    assert holder['ui.node.bg_color'] == '#ff0000'
    
    info = holder.get_info('ui.node.bg_color')
    assert info.source == 'local'
    assert not info.is_overridden


def test_global_override_wins():
    """Test that OVERRIDE mode forces value on all holders."""
    
    registry, holder = create_test_settings_holder(
        predefined_local={'ui.node.bg_color': '#ff0000'}
    )
    
    # Set global override
    registry.set_global('ui.node.bg_color', '#000000', SettingMode.OVERRIDE)
    
    # Override wins over local
    assert holder['ui.node.bg_color'] == '#000000'
    
    info = holder.get_info('ui.node.bg_color')
    assert info.is_overridden
    assert info.source == 'global_override'


def test_with_modified_settings():
    """Test temporary setting modifications."""
    service = create_test_library_system(load_libraries=False)
    registry = service.get_settings_registry()
    
    # Get original values
    original_verbose = registry.resolve('debug.verbose_logging')[0]
    original_font = registry.resolve('ui.node.font_size')[0]
    
    with SettingsTestContext(registry) as ctx:
        ctx.set('debug.verbose_logging', True)
        ctx.set_override('ui.node.font_size', 20)
        
        assert registry.resolve('debug.verbose_logging')[0] == True
        assert registry.resolve('ui.node.font_size')[0] == 20
    
    # Original values restored
    assert registry.resolve('debug.verbose_logging')[0] == original_verbose
    assert registry.resolve('ui.node.font_size')[0] == original_font


def test_settings_context_chaining():
    """Test that context methods can be chained."""
    service = create_test_library_system(load_libraries=False)
    registry = service.get_settings_registry()
    
    with SettingsTestContext(registry) as ctx:
        ctx.set('debug.verbose_logging', True) \
           .set('debug.show_execution_time', True) \
           .set_override('ui.node.font_size', 20)
        
        assert registry.resolve('debug.verbose_logging')[0] == True
        assert registry.resolve('debug.show_execution_time')[0] == True
        assert registry.resolve('ui.node.font_size')[0] == 20


def test_mock_execution_context():
    """Test the mock execution context."""
    ctx = MockExecutionContext()
    
    ctx.log("Starting process")
    ctx.log("Step 1 complete")
    ctx.warn("Low memory")
    ctx.error("Failed to connect")
    
    assert len(ctx.logs) == 2
    assert len(ctx.warnings) == 1
    assert len(ctx.errors) == 1
    
    ctx.set_progress(0.5)
    assert ctx.progress == 0.5
    
    ctx.clear()
    assert len(ctx.logs) == 0
    assert ctx.progress == 0.0


def test_full_system_with_settings():
    """Integration test with full library system."""
    service = create_test_library_system(
        load_libraries=False,  # Faster for this test
        use_temp_settings=True  # Isolated from user settings
    )
    
    # Modify settings via service
    service.set_setting('execution.auto_execute', False)
    
    # Verify
    assert service.get_setting('execution.auto_execute') == False
    
    # Access registry directly
    registry = service.get_settings_registry()
    value, source = registry.resolve('execution.auto_execute')
    assert value == False
    assert source == 'global'
