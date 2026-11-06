"""Fetch records: which files in a cache volume haybale-models fetched, and for which catalog entry.

Records are keyed by the volume key and the path inside the volume, so they follow a volume
that is relocated.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import asdict, dataclass
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FetchRecord:
    """One file haybale-models fetched into a cache volume."""

    volume: str
    relative: str
    sha256: str
    entry_key: str
    address: str
    size: int | None = None
    """Bytes of the file when it was fetched; ``None`` for a record written without one."""

    def current(self, size: int) -> bool:
        """Whether the record still describes a file of *size* bytes; an unknown size always does."""
        return self.size is None or self.size == size


class FetchRecords:
    """A JSON file of :class:`FetchRecord`; safe to read and write from any thread.

    A missing or unreadable file reads as empty. Every change is written atomically.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.RLock()
        self._records: list[FetchRecord] = self._load()
        self._listeners: list[Callable[[], None]] = []

    def add_listener(self, cb: Callable[[], None]) -> None:
        """Call ``cb()`` after a record is added or removed."""
        with self._lock:
            self._listeners.append(cb)

    def remove_listener(self, cb: Callable[[], None]) -> None:
        with self._lock:
            if cb in self._listeners:
                self._listeners.remove(cb)

    def _notify(self) -> None:
        with self._lock:
            listeners = list(self._listeners)
        for cb in listeners:
            try:
                cb()
            except Exception:
                logger.exception("fetch records listener failed")

    def add(self, record: FetchRecord) -> None:
        """Store *record*, replacing any record of the same file."""
        with self._lock:
            self._records = [
                r for r in self._records if (r.volume, r.relative) != (record.volume, record.relative)
            ]
            self._records.append(record)
            self._save()
        self._notify()

    def all(self) -> tuple[FetchRecord, ...]:
        """Every record."""
        with self._lock:
            return tuple(self._records)

    def at(self, volume: str, relative: str) -> list[FetchRecord]:
        """The records of the file at *relative* in *volume*."""
        with self._lock:
            return [r for r in self._records if r.volume == volume and r.relative == relative]

    def for_entry(self, entry_key: str) -> list[FetchRecord]:
        """The records of every file fetched for the catalog entry *entry_key*."""
        with self._lock:
            return [r for r in self._records if r.entry_key == entry_key]

    def remove(self, volume: str, relative: str) -> None:
        """Forget the file at *relative* in *volume*; unknown files are ignored.

        Raises:
            OSError: The file could not be written; the record is forgotten in memory and
                listeners are still called.
        """
        with self._lock:
            kept = [r for r in self._records if not (r.volume == volume and r.relative == relative)]
            if len(kept) == len(self._records):
                return
            self._records = kept
        try:
            with self._lock:
                self._save()
        finally:
            self._notify()

    def _load(self) -> list[FetchRecord]:
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            return [FetchRecord(**row) for row in raw["records"]]
        except FileNotFoundError:
            return []
        except (OSError, ValueError, KeyError, TypeError):
            logger.warning("fetch records at %s are unreadable; starting empty", self._path, exc_info=True)
            return []

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temp = self._path.with_name(self._path.name + ".tmp")
        temp.write_text(json.dumps({"records": [asdict(r) for r in self._records]}, indent=1), "utf-8")
        os.replace(temp, self._path)
