"""LoadedModels — a refcounted pool so nodes share one in-memory load of a model."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable, Hashable
from dataclasses import dataclass, field
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass(frozen=True)
class PoolEntry:
    """A snapshot of one loaded model: its key, how many holders it has, and when it loaded."""

    key: tuple[str, Hashable]
    holders: int
    loaded_at: float


@dataclass
class _Loaded:
    value: Any
    release: Callable[[Any], None]
    loaded_at: float
    holders: dict[int, object] = field(default_factory=dict)


class LoadedModels:
    """Refcounted pool of loaded models, keyed ``(model key, variant key)``.

    The first holder of a key loads it; later holders share the load. When the last holder
    lets go, the model is released at once. Holders are counted as a set: one holder
    acquiring twice counts once.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entries: dict[tuple[str, Hashable], _Loaded] = {}
        self._key_locks: dict[tuple[str, Hashable], threading.Lock] = {}

    def acquire(
        self,
        key: tuple[str, Hashable],
        holder: object,
        load: Callable[[], T],
        release: Callable[[T], None],
    ) -> T:
        """Return the loaded model for *key*, loading it if no one has.

        A second caller for a key being loaded waits for the first, then shares its result.
        If *load* raises, nothing is pooled and the error propagates.
        """
        found = self._join(key, holder)
        if found is not _MISSING:
            return found  # type: ignore[no-any-return]
        with self._lock:
            key_lock = self._key_locks.setdefault(key, threading.Lock())
        with key_lock:
            found = self._join(key, holder)
            if found is not _MISSING:
                return found  # type: ignore[no-any-return]
            value = load()
            entry = _Loaded(value, release, time.time(), {id(holder): holder})
            with self._lock:
                self._entries[key] = entry
            return value

    def _join(self, key: tuple[str, Hashable], holder: object) -> Any:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return _MISSING
            entry.holders[id(holder)] = holder
            return entry.value

    def release(self, holder: object) -> None:
        """Drop *holder* from every key; a key left without holders is released at once."""
        freed: list[_Loaded] = []
        with self._lock:
            for key in list(self._entries):
                entry = self._entries[key]
                if entry.holders.pop(id(holder), None) is not None and not entry.holders:
                    freed.append(self._entries.pop(key))
        self._free(freed)

    def release_all(self) -> None:
        """Release every entry, whatever its holders."""
        with self._lock:
            freed = list(self._entries.values())
            self._entries.clear()
        self._free(freed)

    def entries(self) -> list[PoolEntry]:
        """Snapshot of the loaded models."""
        with self._lock:
            return [PoolEntry(k, len(e.holders), e.loaded_at) for k, e in self._entries.items()]

    @staticmethod
    def _free(freed: list[_Loaded]) -> None:
        for entry in freed:
            try:
                entry.release(entry.value)
            except Exception:
                logger.exception("Releasing a pooled model failed")


_MISSING: Any = object()
