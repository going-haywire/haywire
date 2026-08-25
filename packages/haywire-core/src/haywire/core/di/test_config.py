# haywire/core/di/test_config.py
"""
Test-specific DI configuration for Haywire.

Provides lightweight configurations for different test scenarios.
"""

import tempfile
from pathlib import Path
from typing import Optional, List, Any, TYPE_CHECKING
from injector import Injector

from haywire.barn.builtin.types import BOOL, CHOICES, COLOR, FLOAT, INT, STRING
from ..settings import (
    SettingsRegistry,
    SettingValue,
    FrameworkSettings,
    Settings,
    setting,
)

if TYPE_CHECKING:
    from .config import LibrarySystemService


# ---------------------------------------------------------------------------
# Reusable test schemas
# ---------------------------------------------------------------------------


class _TestFrameworkSettings(FrameworkSettings, namespace="test.global"):
    """Minimal FrameworkSettings for unit tests that need registered global keys."""

    verbose_logging = setting[BOOL](False, label="Verbose Logging")
    font_size = setting[INT](12, label="Font Size", min=8, max=72)


class TestingWidgetSettings(FrameworkSettings, namespace="test.widgets"):
    """FrameworkSettings covering every widget type, for UI harness tests.

    One field per widget branch in _build_field_widget:
      - bool   → ui.switch
      - int    → NumberDrag (step=1)
      - float  → NumberDrag
      - str    → ui.input
      - choices → ui.select
      - color  → ui.color_input
    """

    flag = setting[BOOL](True, label="Flag", description="Boolean — renders as switch", category="types")
    count = setting[INT](
        3, min=0, max=10, label="Count", description="Integer — renders as NumberDrag", category="types"
    )
    ratio = setting[FLOAT](
        0.5, min=0.0, max=1.0, label="Ratio", description="Float — renders as NumberDrag", category="types"
    )
    label = setting[STRING](
        "hello", label="Label", description="String — renders as text input", category="types"
    )
    mode = setting[CHOICES](
        "fast",
        widget_config={"options": ["fast", "balanced", "quality"]},
        label="Mode",
        description="Choices — renders as dropdown",
        category="types",
    )
    tint = setting[COLOR](
        "#ff0000",
        label="Tint",
        description="Color — renders as color picker",
        category="types",
    )


def create_test_injector(
    workspace_root: Optional[str] = None,
    library_paths: Optional[List[str]] = None,
    enable_file_watching: bool = False,
    load_libraries: bool = False,
    settings_path: Optional[str] = None,
    watch_settings: bool = False,
    use_temp_settings: bool = True,
    workspace_settings_path: Optional[str] = None,
) -> Injector:
    """
    Create a test-specific DI injector with minimal overhead.

    ``use_temp_settings`` redirects BOTH settings tiers into a throwaway
    directory. The workspace tier matters most: it is the one the app writes
    back to (a settings descriptor's ``__set__`` calls
    ``registry.save_to_json_debounced()``), and it is derived from
    ``workspace_root`` — which tests pass as the real repo root so library
    discovery works. Left alone, a test that writes any mirrored setting
    persists into the developer's own ``<repo>/.haywire/settings.json`` and
    silently reconfigures their studio.
    """
    from .config import HaywireModule

    if use_temp_settings and (settings_path is None or workspace_settings_path is None):
        temp_dir = tempfile.mkdtemp(prefix="haywire_test_")
        if settings_path is None:
            settings_path = str(Path(temp_dir) / "settings.json")
        if workspace_settings_path is None:
            workspace_settings_path = str(Path(temp_dir) / "workspace-settings.json")

    module = HaywireModule(
        workspace_root=workspace_root,
        library_paths=library_paths,
        enable_file_watching=enable_file_watching,
        settings_path=settings_path,
        watch_settings=watch_settings,
        workspace_settings_path=workspace_settings_path,
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
    workspace_settings_path: Optional[str] = None,
) -> "LibrarySystemService":
    """
    Create library system for integration tests.

    Settings paths are temp-redirected by default — see ``create_test_injector``
    for why the workspace tier in particular must not be the real one.
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
        workspace_settings_path=workspace_settings_path,
    )

    service = LibrarySystemService(injector)

    if load_libraries:
        service.initialize()

    return service


def create_test_settings_registry(
    predefined_settings: Optional[dict] = None, register_builtins: bool = True
) -> "SettingsRegistry":
    """
    Create an isolated settings registry for unit tests.

    Args:
        predefined_settings: Optional dict of {full_key: value} to pre-set.
        register_builtins: Whether to register built-in FrameworkSettings schemas.

    Returns:
        Isolated SettingsRegistry.

    Example:
        registry = create_test_settings_registry({
            'test.global.verbose_logging': True,
        })
    """
    from haywire.barn.builtin.types import BOOL, FLOAT, INT, STRING
    from haywire.core.types.interface import IType

    # define() now requires an IType; map a predefined value's Python type to one.
    _py_to_itype: dict[type, type[IType]] = {bool: BOOL, int: INT, float: FLOAT, str: STRING}

    registry = SettingsRegistry()

    if predefined_settings:
        for name, value in predefined_settings.items():
            if registry.has_definition(name):
                registry.set_global(name, value, tier="global")
            else:
                registry.define(name, value, type_=_py_to_itype.get(type(value), STRING))
                registry.set_global(name, value, tier="global")

    return registry


def create_test_bag(
    bag_cls: type | None = None,
    predefined_local: Optional[dict[str, Any]] = None,
    predefined_global: Optional[dict[str, Any]] = None,
) -> tuple["SettingsRegistry", Any]:
    """
    Create an isolated registry + Settings instance for unit tests.

    The bag is returned as ``Any`` rather than ``Settings``: its fields come
    from ``bag_cls`` (or the default test bag) and are resolved through
    descriptors at runtime, so a static ``Settings`` type would reject every
    real field access (``bag.bg_color``, ``bag.strength``, ...).

    Args:
        bag_cls:           Settings subclass to instantiate.  Defaults to a minimal
                           test settings with bg_color, font_size, verbose fields.
        predefined_local:  {attr_name: value} applied as local instance values.
        predefined_global: {full_key: value} pre-set in the global registry.

    Returns:
        (SettingsRegistry, Settings instance)

    Example:
        class MySettings(Settings):
            strength: float = setting(0.5, min=0.0, max=1.0)

        registry, bag = create_test_bag(MySettings, predefined_local={'strength': 0.8})
        assert bag.strength == 0.8
    """
    if bag_cls is None:

        class _DefaultTestBag(Settings):
            bg_color = setting[COLOR]("#ffffff", label="Background Color")
            font_size = setting[INT](12, min=8, max=72, label="Font Size")
            verbose = setting[BOOL](False, label="Verbose Mode")

        bag_cls = _DefaultTestBag

    registry = create_test_settings_registry(predefined_settings=predefined_global)
    bag = bag_cls(registry=registry)
    bag._subscribe_settings()

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

    def __init__(self, registry: "SettingsRegistry"):
        self.registry = registry
        self._original_values: dict = {}

    def __enter__(self) -> "SettingsTestContext":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        for name, original in self._original_values.items():
            if original is None or not original.is_set:
                self.registry.reset_global(name, tier="workspace")
            else:
                self.registry.set_global(name, original.value, tier="workspace")
        return False

    def set(self, name: str, value: Any) -> None:
        """Set a setting value."""
        self._save_original(name)
        self.registry.set_global(name, value)

    def reset(self, name: str) -> None:
        """Reset a setting to unset."""
        self._save_original(name)
        self.registry.reset_global(name)

    def _save_original(self, name: str) -> None:
        if name not in self._original_values:
            sv = self.registry.get_global(name)
            self._original_values[name] = SettingValue(is_set=sv.is_set, value=sv.value) if sv else None
