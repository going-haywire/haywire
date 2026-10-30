"""The ``~/.haywire/volumes.toml`` file: where each volume lives on this machine."""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from haywire.core.tomlio import edit_toml, plain, read_toml
from haywire.core.volumes.volume import VOLUME_NAME_RE, volume_by_name

logger = logging.getLogger(__name__)

__all__ = ["VolumeStore", "get_volume_store", "set_volume_store"]


class VolumeStore:
    """Reads and writes volume locations in a ``[volumes]`` TOML table.

    The file is re-read whenever its modification time or size changes.
    Malformed files and entries with an invalid name or a non-absolute location
    are logged and ignored.
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path: Path = path if path is not None else Path.home() / ".haywire" / "volumes.toml"
        self._lock = threading.RLock()
        self._stamp: tuple[int, int] | None = None
        self._cache: dict[str, Path] = {}

    def configured(self) -> dict[str, Path]:
        """Return valid ``name -> absolute location`` entries; ``{}`` if the file is missing or invalid."""
        with self._lock:
            try:
                st = self.path.stat()
            except OSError:
                self._stamp, self._cache = None, {}
                return {}
            stamp = (st.st_mtime_ns, st.st_size)
            if stamp != self._stamp:
                self._cache = self._load()
                self._stamp = stamp
            return dict(self._cache)

    def _load(self) -> dict[str, Path]:
        try:
            doc = plain(read_toml(self.path))
        except Exception as exc:
            logger.error("Ignoring unreadable volumes file %s: %s", self.path, exc)
            return {}
        table = doc.get("volumes", {})
        if not isinstance(table, dict):
            logger.warning("Ignoring %s: [volumes] is not a table", self.path)
            return {}
        result: dict[str, Path] = {}
        for name, location in table.items():
            if not VOLUME_NAME_RE.match(name):
                logger.warning("Ignoring volume %r in %s: invalid name", name, self.path)
            elif not isinstance(location, str) or not Path(location).is_absolute():
                logger.warning(
                    "Ignoring volume %r in %s: location must be an absolute path", name, self.path
                )
            else:
                result[name] = Path(location)
        return result

    def set(self, name: str, location: Path) -> None:
        """Define or replace *name*'s location.

        Raises ``ValueError`` if *name* is invalid, names a declared
        non-configurable volume, or *location* is not absolute.
        """
        if not VOLUME_NAME_RE.match(name):
            raise ValueError(f"Invalid volume name {name!r}")
        declared = volume_by_name(name)
        if declared is not None and not declared.configurable:
            raise ValueError(f"Volume {name!r} is not configurable")
        if not location.is_absolute():
            raise ValueError(f"Volume location must be absolute: {location}")
        with self._lock:
            self._ensure_file()
            with edit_toml(self.path) as doc:
                doc["volumes"][name] = str(location)

    def remove(self, name: str) -> bool:
        """Delete *name*'s entry. Return whether it existed."""
        with self._lock:
            if not self.path.exists():
                return False
            with edit_toml(self.path) as doc:
                table = doc.get("volumes")
                if table is None or name not in table:
                    return False
                del table[name]
                return True

    def _ensure_file(self) -> None:
        if not self.path.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text("[volumes]\n", encoding="utf-8")
            return
        with edit_toml(self.path) as doc:
            if "volumes" not in doc:
                doc["volumes"] = {}


_store: VolumeStore | None = None


def get_volume_store() -> VolumeStore:
    """Return the ambient store, creating the default (``~/.haywire/volumes.toml``) on first use."""
    global _store
    if _store is None:
        _store = VolumeStore()
    return _store


def set_volume_store(store: VolumeStore | None) -> None:
    """Install *store* as the ambient store; ``None`` restores lazy default creation."""
    global _store
    _store = store
