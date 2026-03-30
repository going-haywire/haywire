# haywire/ui/prefs/logging_configurator.py
"""Applies DebugSettings log levels to the Python logging hierarchy at runtime."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .debug_settings import DebugSettings

# Maps DebugSettings attribute name → Python logger namespace
_GROUP_MAP: dict[str, str] = {
    "log_execution": "haywire.core.execution",
    "log_assembly": "haywire.core.assembly",
    "log_graph": "haywire.core.graph",
    "log_settings": "haywire.core.settings",
    "log_library": "haywire.core.library",
    "log_ui": "haywire.ui",
}

_ROOT_NAMESPACE = "haywire"


class LoggingConfigurator:
    """
    Watches DebugSettings and applies log levels to the Python logging hierarchy.

    Instantiate with no arguments — creates its own DebugSettings instance
    (requires SettingsRegistry to already be wired). Applies current levels
    immediately and subscribes for future changes.
    """

    def __init__(self) -> None:
        from .debug_settings import DebugSettings  # noqa: PLC0415

        self._settings: DebugSettings = DebugSettings()
        self._apply_all()
        self._settings.subscribe(self._on_setting_change)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

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
            # "" → inherit: reset to NOTSET so the parent level propagates
            logger.setLevel(logging.NOTSET)

    def _on_setting_change(self, name: str, value: object, old: object) -> None:
        if name == "log_level":
            self._apply_root(str(value))
        elif name in _GROUP_MAP:
            self._apply_group(_GROUP_MAP[name], str(value) if value else "")
