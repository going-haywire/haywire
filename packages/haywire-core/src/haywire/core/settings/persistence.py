# haywire/core/settings/persistence.py
"""
File persistence for SettingsRegistry — JSON in/out + watching.

The store reads files into flat {dot.key: entry} dicts and writes them back;
all interpretation (rehydration, auto-define, tiers) stays in the registry.
"""

from __future__ import annotations
from typing import Any, Callable
import threading
import logging
import time
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class SettingsFileStore(object):
    """Pure file I/O collaborator for SettingsRegistry.

    Knows nothing about setting definitions, tiers, descriptors, or
    SettingValue — only flat dot-key dicts, JSON files, and watchdog
    observers.
    """

    _SAVE_DEBOUNCE: float = 0.5  # seconds

    def __init__(self) -> None:
        self._observers: list = []
        self._save_timer: threading.Timer | None = None

    # =========================================================================
    # Read / Write
    # =========================================================================

    def read(self, path: Path) -> dict[str, Any] | None:
        """Parse a JSON file and return its flat {dot.key: entry} form.

        Returns None (and logs) if the file can't be parsed.
        """
        try:
            with open(path, "r") as f:
                data = json.load(f)
        except Exception as e:
            logger.error(f"Failed to parse settings file: {e}")
            return None

        return self._flatten(data)

    def write(self, path: Path, entries: dict[str, Any]) -> None:
        """Nest flat dot-key *entries* and write them as JSON to *path*."""
        data: dict[str, Any] = {}
        for name, value in entries.items():
            self._set_nested(data, name, value)

        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w") as f:
            json.dump(data, f, indent=2, sort_keys=True)

        logger.info(f"Settings saved to {path}")

    def write_debounced(self, path: Path, provider: Callable[[], dict[str, Any]]) -> None:
        """Schedule a debounced write.

        Each call resets the timer so that the file write only happens once
        the caller stops requesting saves for `_SAVE_DEBOUNCE` seconds.
        *provider* is called (on the timer thread) to produce the entries to
        write at fire time — not at schedule time.
        """
        if self._save_timer is not None:
            self._save_timer.cancel()
        self._save_timer = threading.Timer(self._SAVE_DEBOUNCE, lambda: self.write(path, provider()))
        self._save_timer.daemon = True
        self._save_timer.start()

    # =========================================================================
    # Flatten / Nest
    # =========================================================================

    def _flatten(self, data: dict, prefix: str = "") -> dict[str, Any]:
        """
        Flatten nested JSON to dot-notation keys.

        A dict is a "setting entry" (not namespace) if it contains
        any of: 'value', 'override', 'default', 'type', 'mode'
        """
        result = {}
        # 'override'/'mode' are retained here (post-P2) only so a legacy
        # {override=true, value=…} table is still recognised as a *setting entry*
        # (not a namespace) and routed through the registry's _parse_config_dict,
        # which strips the override flag and reads it as a plain set value.
        setting_keys = {
            "value",
            "override",
            "default",
            "type",
            "mode",
            "label",
            "category",
            "min_value",
            "max_value",
            "choices",
        }

        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key

            if isinstance(value, dict):
                if any(k in value for k in setting_keys):
                    result[full_key] = value
                else:
                    result.update(self._flatten(value, full_key))
            else:
                result[full_key] = value

        return result

    def _set_nested(self, data: dict, name: str, value: Any) -> None:
        """Set a value in nested dict using dot-notation key."""
        parts = name.split(".")
        current = data
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value

    # =========================================================================
    # File Watching
    # =========================================================================

    def watch(self, path: Path, on_change: Callable[[], None]) -> None:
        """Watch *path*'s parent directory for changes and invoke *on_change*.

        *on_change* is called (debounced, 0.5s) whenever *path* itself is
        modified.
        """
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler
        except ImportError:
            logger.warning(
                "watchdog not installed, file watching disabled. Install with: pip install watchdog"
            )
            return

        class ConfigHandler(FileSystemEventHandler):
            def __init__(self):
                self._debounce_time: float = 0.0

            def on_modified(self, event):
                now = time.time()
                if now - self._debounce_time < 0.5:
                    return
                self._debounce_time = now

                if Path(event.src_path).resolve() == path:
                    logger.info(f"Settings file changed ({path}), reloading...")
                    try:
                        on_change()
                    except Exception as e:
                        logger.error(f"Failed to reload settings: {e}")

        # The settings file may not exist yet ("create on save"), which means
        # its parent directory may also be absent. Linux inotify raises when
        # asked to watch a non-existent directory (macOS FSEvents tolerates
        # it), so ensure the directory exists before scheduling the observer.
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.warning(f"Could not create settings dir {path.parent}; watching disabled: {e}")
            return

        observer = Observer()
        observer.schedule(ConfigHandler(), str(path.parent), recursive=False)
        try:
            observer.start()
        except OSError as e:
            # File watching is non-essential; never let it break app init.
            logger.warning(f"Could not start settings watcher for {path}; hot-reload disabled: {e}")
            return

        self._observers.append(observer)
        logger.info(f"Watching settings file: {path}")

    def stop(self) -> None:
        """Stop all file watchers.

        ``join`` is bounded so a watchdog observer thread that fails to
        terminate (seen with the macOS FSEvents backend) degrades to a warning
        instead of wedging the caller — the watcher is non-essential, and an
        unbounded ``join()`` here can hang app shutdown or a whole test suite.
        """
        for observer in self._observers:
            observer.stop()
            observer.join(timeout=2.0)
            if observer.is_alive():
                logger.warning("Settings watcher thread did not stop within 2s; abandoning.")
        self._observers = []
