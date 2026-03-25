# haywire/core/di/test_config.py
"""
Test-specific DI configuration for Haywire.

Provides lightweight configurations for different test scenarios.
"""

import tempfile
from pathlib import Path
from typing import Optional, List, Any, TYPE_CHECKING
from injector import Injector

from ..settings import GlobalSettingsRegistry, SettingMode, SettingValue, GlobalSettings, Settings, setting

if TYPE_CHECKING:
    from .config import LibrarySystemService


# ---------------------------------------------------------------------------
# Reusable test schemas
# ---------------------------------------------------------------------------


class _TestGlobalSettings(GlobalSettings, namespace="test.global"):
    """Minimal GlobalSettings for unit tests that need registered global keys."""

    verbose_logging: bool = setting(False, label="Verbose Logging")
    font_size: int = setting(12, label="Font Size", min=8, max=72)


def create_test_injector(
    workspace_root: Optional[str] = None,
    library_paths: Optional[List[str]] = None,
    enable_file_watching: bool = False,
    load_libraries: bool = False,
    settings_path: Optional[str] = None,
    watch_settings: bool = False,
    use_temp_settings: bool = True,
) -> Injector:
    """
    Create a test-specific DI injector with minimal overhead.
    """
    from .config import HaywireModule

    if settings_path is None and use_temp_settings:
        temp_dir = tempfile.mkdtemp(prefix="haywire_test_")
        settings_path = str(Path(temp_dir) / "settings.toml")

    module = HaywireModule(
        workspace_root=workspace_root,
        library_paths=library_paths,
        enable_file_watching=enable_file_watching,
        settings_path=settings_path,
        watch_settings=watch_settings,
    )

    return Injector([module])


def create_test_library_system(
    workspace_root: Optional[str] = None,
    library_paths: Optional[List[str]] = None,
    load_libraries: bool = True,
    enable_file_watching: bool = False,
    settings_path: Optional[str] = None,
    watch_settings: bool = False,
    use_temp_settings: bool = True,
) -> "LibrarySystemService":
    """
    Create library system for integration tests.
    """
    from .config import LibrarySystemService

    injector = create_test_injector(
        workspace_root=workspace_root,
        library_paths=library_paths,
        enable_file_watching=enable_file_watching,
        load_libraries=load_libraries,
        settings_path=settings_path,
        watch_settings=watch_settings,
        use_temp_settings=use_temp_settings,
    )

    service = LibrarySystemService(injector)

    if load_libraries:
        service.initialize()

    return service


def create_test_settings_registry(
    predefined_settings: Optional[dict] = None, register_builtins: bool = True
) -> "GlobalSettingsRegistry":
    """
    Create an isolated settings registry for unit tests.

    Args:
        predefined_settings: Optional dict of {full_key: value} to pre-set.
        register_builtins: Whether to register built-in GlobalSettings schemas.

    Returns:
        Isolated GlobalSettingsRegistry.

    Example:
        registry = create_test_settings_registry({
            'test.global.verbose_logging': True,
        })
    """
    registry = GlobalSettingsRegistry()

    if predefined_settings:
        for name, value in predefined_settings.items():
            if registry.has_definition(name):
                registry.set_global(name, value, SettingMode.SET, tier="global")
            else:
                registry.define(name, value)
                registry.set_global(name, value, SettingMode.SET, tier="global")

    return registry


def create_test_bag(
    bag_cls: type = None,
    predefined_local: Optional[dict[str, Any]] = None,
    predefined_global: Optional[dict[str, Any]] = None,
) -> tuple["GlobalSettingsRegistry", Settings]:
    """
    Create an isolated registry + Settings instance for unit tests.

    Args:
        bag_cls:           Settings subclass to instantiate.  Defaults to a minimal
                           test settings with bg_color, font_size, verbose fields.
        predefined_local:  {attr_name: value} applied as local instance values.
        predefined_global: {full_key: value} pre-set in the global registry.

    Returns:
        (GlobalSettingsRegistry, Settings instance)

    Example:
        class MySettings(Settings):
            strength: float = setting(0.5, min=0.0, max=1.0)

        registry, bag = create_test_bag(MySettings, predefined_local={'strength': 0.8})
        assert bag.strength == 0.8
    """
    if bag_cls is None:

        class _DefaultTestBag(Settings):
            bg_color: str = setting("#ffffff", label="Background Color")
            font_size: int = setting(12, min=8, max=72, label="Font Size")
            verbose: bool = setting(False, label="Verbose Mode")

        bag_cls = _DefaultTestBag

    registry = create_test_settings_registry(predefined_settings=predefined_global)
    bag = bag_cls(registry=registry)
    bag._subscribe_mirrors()

    if predefined_local:
        for name, value in predefined_local.items():
            setattr(bag, name, value)

    return registry, bag


class SettingsTestContext:
    """
    Context manager for temporarily modifying global settings in tests.

    Automatically restores original values after the test.

    Example:
        with SettingsTestContext(registry) as ctx:
            ctx.set('test.global.font_size', 16)
            # Test code here uses modified settings
        # Original settings restored automatically
    """

    def __init__(self, registry: "GlobalSettingsRegistry"):
        self.registry = registry
        self._original_values: dict = {}

    def __enter__(self) -> "SettingsTestContext":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        for name, original in self._original_values.items():
            if original is None or original.mode == SettingMode.AUTO:
                self.registry.reset_global(name, tier="workspace")
            else:
                self.registry.set_global(name, original.value, original.mode, tier="workspace")
        return False

    def set(self, name: str, value: Any) -> None:
        """Set a setting value (SET mode)."""
        self._save_original(name)
        self.registry.set_global(name, value, SettingMode.SET)

    def set_override(self, name: str, value: Any) -> None:
        """Set a setting value with OVERRIDE mode."""
        self._save_original(name)
        self.registry.set_global(name, value, SettingMode.OVERRIDE)

    def reset(self, name: str) -> None:
        """Reset a setting to AUTO."""
        self._save_original(name)
        self.registry.reset_global(name)

    def _save_original(self, name: str) -> None:
        if name not in self._original_values:
            sv = self.registry.get_global(name)
            self._original_values[name] = SettingValue(mode=sv.mode, value=sv.value) if sv else None
