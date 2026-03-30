# haywire/core/debug/configurator.py
"""Applies DebugSettings log levels to the Python logging hierarchy at runtime."""

import logging

from .keys import LIBRARY_LOG_PREFIX, lib_id_from_key
from .debug_settings import DebugSettings
from ..settings.registry import SettingsRegistry
from ..settings.value import SettingValue

# Maps DebugSettings attribute name → Python logger namespace
_GROUP_MAP: dict[str, str] = {
    "log_execution": "haywire.core.execution",
    "log_assembly": "haywire.core.assembly",
    "log_graph": "haywire.core.graph",
    "log_settings": "haywire.core.settings",
    "log_library": "haywire.core.library",
    "log_registry": "haywire.core.registry",
    "log_node": "haywire.core.node",
    "log_ui": "haywire.ui",
}

_ROOT_NAMESPACE = "haywire"


class LoggingConfigurator:
    """
    Watches DebugSettings and applies log levels to the Python logging hierarchy.

    Instantiate with no arguments — creates its own DebugSettings instance
    (requires SettingsRegistry to already be wired). Applies current levels
    immediately and subscribes for future changes.

    Also subscribes to SettingsRegistry to dynamically handle per-library
    log level settings registered under debug.library.<lib_id>.log_level.
    """

    def __init__(self, debug_settings: DebugSettings | None = None) -> None:
        self._settings: DebugSettings = debug_settings if debug_settings is not None else DebugSettings()

        # lib_id → module_name for dynamically registered library loggers
        self._library_namespaces: dict[str, str] = {}

        self._apply_all()
        self._settings.subscribe(self._on_setting_change)

    def attach_registry(self, registry: "SettingsRegistry") -> None:
        """Attach a SettingsRegistry to handle dynamic debug.library.* keys.

        Called after construction when the registry becomes available.
        """
        self._attach_registry(registry)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _attach_registry(self, registry: "SettingsRegistry") -> None:
        # Scan already-defined library keys (libraries loaded before configurator)
        for key in list(registry.all_definitions()):
            if key.startswith(LIBRARY_LOG_PREFIX + "."):
                self._register_library_from_key(key, registry)
                try:
                    value, _ = registry.resolve(key)
                    self._apply_library_level(key, value)
                except KeyError:
                    pass
        registry.add_listener(lambda name, sv: self._on_registry_change(name, sv, registry))

    def _register_library_from_key(self, key: str, registry: "SettingsRegistry") -> None:
        lib_id = lib_id_from_key(key)
        if lib_id and lib_id not in self._library_namespaces:
            meta = registry.get_definition_metadata(key)
            module_name = meta.get("module_name", lib_id)
            self._library_namespaces[lib_id] = module_name

    def _apply_all(self) -> None:
        """Set initial log levels from current settings values."""
        self._apply_root(self._settings.log_level)
        for attr, namespace in _GROUP_MAP.items():
            self._apply_group(namespace, getattr(self._settings, attr))

    def _apply_root(self, level: str) -> None:
        logging.getLogger(_ROOT_NAMESPACE).setLevel(level)

    def _apply_group(self, namespace: str, level: str) -> None:
        logger = logging.getLogger(namespace)
        if level:
            logger.setLevel(level)
        else:
            logger.setLevel(logging.NOTSET)

    def _apply_library_level(self, key: str, level: str) -> None:
        lib_id = lib_id_from_key(key)
        if lib_id is None:
            return
        module_name = self._library_namespaces.get(lib_id, lib_id)
        self._apply_group(module_name, level)

    def _on_setting_change(self, name: str, value: object, old: object) -> None:
        if name == "log_level":
            self._apply_root(str(value))
        elif name in _GROUP_MAP:
            self._apply_group(_GROUP_MAP[name], str(value) if value else "")

    def _on_registry_change(self, name: str, sv: "SettingValue", registry: "SettingsRegistry") -> None:
        from haywire.core.settings.enums import SettingMode  # noqa: PLC0415

        if not name.startswith(LIBRARY_LOG_PREFIX + "."):
            return

        lib_id = lib_id_from_key(name)
        if lib_id is None:
            return

        if name not in registry:
            # Key was undefined — reset logger and remove mapping
            module_name = self._library_namespaces.pop(lib_id, lib_id)
            logging.getLogger(module_name).setLevel(logging.NOTSET)
            return

        # New definition (AUTO) or value change
        self._register_library_from_key(name, registry)

        if sv.mode == SettingMode.AUTO:
            # Newly defined — apply default (inherit)
            self._apply_library_level(name, "")
        else:
            self._apply_library_level(name, str(sv.value) if sv.value else "")
