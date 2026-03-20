# haywire/core/di/test_config.py
"""
Test-specific DI configuration for Haywire.

Provides lightweight configurations for different test scenarios.
"""

import tempfile
from pathlib import Path
from typing import Optional, List, Any, TYPE_CHECKING
from injector import Injector

from ..settings import (
    GlobalSettingsRegistry, SettingsHolder, SettingMode, SettingValue,
    NodeSettings, GlobalSettings, setting, Color,
)

if TYPE_CHECKING:
    from .config import LibrarySystemService


# ---------------------------------------------------------------------------
# Reusable test schema — used by create_test_settings_holder and tests below
# ---------------------------------------------------------------------------

class _TestNodeSettings(NodeSettings, namespace='test.node'):
    bg_color: Color = setting('#ffffff', label='Background Color')
    font_size: int = setting(12, label='Font Size', min=8, max=72)
    verbose: bool = setting(False, label='Verbose Mode')


class _TestGlobalSettings(GlobalSettings, namespace='test.global'):
    """Minimal GlobalSettings for unit tests that need registered global keys."""
    verbose_logging: bool = setting(False, label='Verbose Logging')
    font_size:       int  = setting(12,    label='Font Size', min=8, max=72)


def create_test_injector(
    workspace_root: Optional[str] = None,
    library_paths: Optional[List[str]] = None,
    enable_file_watching: bool = False,
    load_libraries: bool = False,
    settings_path: Optional[str] = None,
    watch_settings: bool = False,
    use_temp_settings: bool = True
) -> Injector:
    """
    Create a test-specific DI injector with minimal overhead.

    Args:
        workspace_root:       Root path (auto-detected if None).
        library_paths:        Additional library paths.
        enable_file_watching: Disable for faster tests.
        load_libraries:       Whether to load libraries (slow, integration only).
        settings_path:        Path to global settings TOML (default: temp file for isolation).
        watch_settings:       Disable for faster tests.
        use_temp_settings:    If True and settings_path is None, use a temp file
                              to isolate tests from user settings.

    Returns:
        Configured test injector.
    """
    # Import here to avoid circular imports at module level
    from .config import HaywireModule

    # Use temp file for settings by default to isolate tests
    if settings_path is None and use_temp_settings:
        temp_dir = tempfile.mkdtemp(prefix='haywire_test_')
        settings_path = str(Path(temp_dir) / 'settings.toml')

    module = HaywireModule(
        workspace_root=workspace_root,
        library_paths=library_paths,
        enable_file_watching=enable_file_watching,
        settings_path=settings_path,
        watch_settings=watch_settings
    )

    return Injector([module])


def create_test_library_system(
    workspace_root: Optional[str] = None,
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
        workspace_root:       Root path (auto-detected if None).
        library_paths:        Additional library paths.
        load_libraries:       Whether to initialize libraries.
        enable_file_watching: Usually False for tests.
        settings_path:        Path to global settings TOML (default: temp file for isolation).
        watch_settings:       Usually False for tests.
        use_temp_settings:    If True, use temp file to isolate from user settings.

    Returns:
        LibrarySystemService (initialized if load_libraries=True).
    """
    # Import here to avoid circular imports
    from .config import LibrarySystemService

    injector = create_test_injector(
        workspace_root=workspace_root,
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
    
    registry = GlobalSettingsRegistry()
        
    # Apply predefined settings into the global tier (simulating hand-edited TOML)
    if predefined_settings:
        for name, value in predefined_settings.items():
            if registry.has_definition(name):
                registry.set_global(name, value, SettingMode.SET, tier='global')
            else:
                # Auto-define if not a builtin
                registry.define(name, value)
                registry.set_global(name, value, SettingMode.SET, tier='global')
    
    return registry


def create_test_settings_holder(
    predefined_local: Optional[dict[str, Any]] = None,
    predefined_global: Optional[dict[str, Any]] = None,
    register_builtins: bool = True,
    schema_cls: type = None,
) -> tuple['GlobalSettingsRegistry', 'SettingsHolder']:
    """
    Create an isolated registry + SettingsHolder for unit tests.

    Uses _TestNodeSettings (namespace='test.node') by default.
    predefined_local keys are short attr names ('bg_color', 'font_size', ...).
    predefined_global keys are full keys ('test.node.bg_color', ...).

    Args:
        predefined_local:  {attr_name: value} applied as local instance values.
        predefined_global: {full_key: value}  pre-set in the global registry.
        register_builtins: Whether to register built-in GlobalSettings schemas.
        schema_cls:        Override the NodeSettings schema class.

    Returns:
        (GlobalSettingsRegistry, SettingsHolder)
    """
    registry = create_test_settings_registry(
        predefined_settings=predefined_global,
        register_builtins=register_builtins,
    )

    # Register schema fields in the global registry so set_global() works.
    resolved_schema = schema_cls or _TestNodeSettings
    for descriptor in resolved_schema._fields.values():
        if descriptor._field_key and not registry.has_definition(descriptor._field_key):
            registry.define(
                descriptor._field_key,
                descriptor._default,
                label=descriptor._label,
                description=descriptor._description,
                category=descriptor._category or 'test',
            )

    from haywire.core.node.properties import NodeProperties
    holder = SettingsHolder(
        schemas={'test': resolved_schema, '_node': NodeProperties},
        registry=registry,
        node_instance=None,
    )

    if predefined_local:
        for name, value in predefined_local.items():
            holder.test.set(name, value)

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
        # Restore original workspace-tier values
        from ..settings import SettingMode

        for name, original in self._original_values.items():
            if original is None or original.mode == SettingMode.AUTO:
                self.registry.reset_global(name, tier='workspace')
            else:
                self.registry.set_global(name, original.value, original.mode, tier='workspace')

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
        """Save original effective global value if not already saved."""
        if name not in self._original_values:
            sv = self.registry.get_global(name)
            self._original_values[name] = SettingValue(mode=sv.mode, value=sv.value) if sv else None