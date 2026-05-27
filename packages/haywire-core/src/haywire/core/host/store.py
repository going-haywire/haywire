"""HostStore — host-provided persistence for engine bootstrap state.

A tiny key/value store that the host application constructs *before* the
DI container is built and passes in as a singleton. Used by engine
services (currently: ``LibraryRegistry``) that need to read or write
persistent state at moments when the ``SettingsRegistry`` is either not
yet available or is the wrong tool — typically at startup, before any
library has enabled.

Two-mechanism design (recorded in ADR-0001):

* **HostStore** owns engine bootstrap config that the engine reads to
  decide *how* to start up (e.g. ``[libraries] disabled`` — which
  libraries to skip before ``enable_all_libraries()`` runs). Read by the
  engine; written by host-config-aware code paths (the marketplace UI's
  enable/disable buttons).

* **SettingsRegistry** keeps doing what it does for library-contributed
  ``LibrarySettings`` and framework-internal ``FrameworkSettings``
  (themes, edge styling, etc.). User and library preferences.

The split honours a real boundary: ``HostStore`` is read *before* any
library is loaded; ``SettingsRegistry`` extends as libraries load. Trying
to use one for both creates a bidirectional dependency between the
library registry and the settings registry (the cycle ADR-0001 §
'Persistence' calls out).

Optional by construction
------------------------
``HostStore`` is a constructor argument to the DI container, not a
global. Hosts that don't supply a file path get an in-memory store
(reads return defaults, writes are kept in memory only). This is the
graceful-degradation path for:

* tests that don't care about persistence
* programmatic/embedded uses of the engine with no workspace
* CI environments that should not write to disk

The host decides; the engine doesn't impose a persistence policy.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import toml

logger = logging.getLogger(__name__)


class HostStore:
    """Sectioned key/value store backed by a TOML file (or in-memory).

    Section names map to top-level TOML tables; keys map to entries
    within that table. Values are whatever TOML can represent (scalars,
    lists, nested dicts).

    Construction
    ------------
    ``HostStore(path)`` reads ``path`` eagerly into memory if the file
    exists. ``path=None`` (or ``HostStore.in_memory()``) creates a
    detached store whose writes are kept in memory only.

    Writes are not debounced — each ``set()`` rewrites the file
    immediately. The expected write rate is low (user clicks "disable
    library", install/uninstall completes) so the simplicity wins over
    debouncing. If a future caller needs high-frequency writes, add
    debouncing here without changing the API.
    """

    def __init__(self, path: Path | str | None = None) -> None:
        self._path: Path | None = Path(path) if path is not None else None
        self._data: dict[str, dict[str, Any]] = {}
        if self._path is not None and self._path.is_file():
            try:
                raw = toml.loads(self._path.read_text())
            except Exception as exc:
                logger.warning(
                    "HostStore: failed to parse %s — starting with empty state (%s)",
                    self._path,
                    exc,
                )
                raw = {}
            # Only top-level dict entries are valid sections; ignore stray scalars.
            self._data = {k: v for k, v in raw.items() if isinstance(v, dict)}

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def in_memory(cls) -> "HostStore":
        """Create a detached store with no file backing. Writes never hit disk."""
        return cls(path=None)

    # ------------------------------------------------------------------
    # Read / write API
    # ------------------------------------------------------------------

    def get(self, section: str, key: str, default: Any = None) -> Any:
        """Return the stored value, or ``default`` if section/key is absent."""
        return self._data.get(section, {}).get(key, default)

    def set(self, section: str, key: str, value: Any) -> None:
        """Set the value and persist to disk (if file-backed)."""
        self._data.setdefault(section, {})[key] = value
        self._flush()

    def remove(self, section: str, key: str) -> None:
        """Drop a key. Removes the section entirely if it becomes empty."""
        sect = self._data.get(section)
        if not sect or key not in sect:
            return
        del sect[key]
        if not sect:
            del self._data[section]
        self._flush()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _flush(self) -> None:
        """Write the in-memory state to disk. No-op for in-memory stores."""
        if self._path is None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(toml.dumps(self._data))
