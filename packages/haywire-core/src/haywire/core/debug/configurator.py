# haywire/core/debug/configurator.py
"""Applies DebugSettings log levels to the Python logging hierarchy at runtime."""

import logging

from ..namespaces import NAMESPACE_LIBRARY_LOG

from .keys import LIBRARY_LOG_LEVEL_FIELD_METATADATA_KEY, lib_id_from_key
from .debug_settings import GLOBAL_BASELINE_LOG_LEVEL_KEY, DebugSettings
from ..settings.registry import SettingsRegistry
from ..settings.value import FieldValue
from ..settings.enums import FieldMode

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

    Construct with the SettingsRegistry to wire dynamic debug.library.* keys.
    Applies current levels immediately and subscribes for future changes.
    """

    def __init__(
        self,
        registry: "SettingsRegistry",
        debug_settings: DebugSettings | None = None,
    ) -> None:
        self._settings: DebugSettings = debug_settings if debug_settings is not None else DebugSettings()

        # lib_id → module_name for dynamically registered library loggers
        self._library_namespaces: dict[str, str] = {}
        self._registry: SettingsRegistry = registry

        self._apply_all()
        self._settings.subscribe(self._on_setting_change)
        self._attach_registry(registry)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _attach_registry(self, registry: "SettingsRegistry") -> None:
        """
        Scan already-defined library keys (libraries loaded before configurator)
        and apply their levels, then subscribe for future changes.
        """
        for key in list(registry.all_definitions()):
            if key.startswith(NAMESPACE_LIBRARY_LOG + "."):
                self._register_library_from_key(key, registry)
                try:
                    value, _ = registry.resolve(key)
                    self._apply_library_level(key, value)
                except KeyError:
                    pass
        registry.subscribe(None, self._on_registry_change)

    def _register_library_from_key(self, key: str, registry: "SettingsRegistry") -> None:
        lib_id = lib_id_from_key(key)
        if lib_id and lib_id not in self._library_namespaces:
            defn = registry.get_definition(key)
            module_name = (
                defn._metadata.get(LIBRARY_LOG_LEVEL_FIELD_METATADATA_KEY, lib_id) if defn else lib_id
            )
            self._library_namespaces[lib_id] = module_name

    def _apply_all(self) -> None:
        """Set initial log levels from current settings values."""
        self._apply_root(self._settings.log_level)
        for attr, namespace in _GROUP_MAP.items():
            self._apply_group(namespace, getattr(self._settings, attr))

    def _apply_root(self, level: str) -> None:
        """Apply the global baseline log level to the root logger."""
        logging.getLogger(_ROOT_NAMESPACE).setLevel(level)

    def _apply_group(self, namespace: str, level: str) -> None:
        """
        Apply a log level to a specific logger namespace.
        namespace: the logger namespace to apply the level to (e.g. "haywire.core.execution"
        level: the log level to apply (e.g. "DEBUG" or "" to inherit)
        """
        logger = logging.getLogger(namespace)
        if level:
            logger.setLevel(level)
        else:
            logger.setLevel(logging.NOTSET)

    def _apply_library_level(self, library_log_level_key: str, level: str) -> None:
        """Apply a log level to a library"""
        lib_id = lib_id_from_key(library_log_level_key)
        if lib_id is None:
            return
        module_name = self._library_namespaces.get(lib_id, lib_id)
        self._apply_group(module_name, level)

    def _on_setting_change(self, name: str, value: object, old: object) -> None:
        """Callback for DebugSettings changes — apply log level changes to the logging hierarchy."""
        if name == GLOBAL_BASELINE_LOG_LEVEL_KEY:
            self._apply_root(str(value))
        elif name in _GROUP_MAP:
            self._apply_group(_GROUP_MAP[name], str(value) if value else "")

    def _on_registry_change(self, name: str, sv: "FieldValue") -> None:
        """Callback for SettingsRegistry changes — handle dynamic debug.library.<lib_id>.log_level keys."""
        if not name.startswith(NAMESPACE_LIBRARY_LOG + "."):
            return

        lib_id = lib_id_from_key(name)
        if lib_id is None:
            return

        if name not in self._registry:
            # Key was undefined — reset logger and remove mapping
            module_name = self._library_namespaces.pop(lib_id, lib_id)
            logging.getLogger(module_name).setLevel(logging.NOTSET)
            return

        # New definition (AUTO) or value change
        self._register_library_from_key(name, self._registry)

        if sv.mode == FieldMode.INHERIT:
            # Newly defined — apply default (inherit)
            self._apply_library_level(name, "")
        else:
            self._apply_library_level(name, str(sv.value) if sv.value else "")
