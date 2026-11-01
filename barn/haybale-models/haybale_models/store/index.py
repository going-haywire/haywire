"""Digest index of the ``models`` volume: which file on disk has which sha256."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

from haybale_models.keys import MODELS_VOLUME

from haywire.core.volumes import VolumeError, location_of

logger = logging.getLogger(__name__)

INDEX_NAME = ".index.json"
_CHUNK = 1024 * 1024
_SKIP_SUFFIXES = (".part",)


@dataclass(frozen=True)
class IndexRecord:
    """One indexed file. ``relative`` is POSIX, relative to the volume location."""

    sha256: str
    relative: str
    size: int
    mtime_ns: int
    source: str | None = None


class ModelIndex:
    """Digest index persisted at ``<volume>/.index.json``.

    Scanning only ``stat``s files; hashing is a separate, explicit step so the caller
    chooses the thread. A moved file keeps its old record's ``source`` because the
    record is re-found by digest.
    """

    def __init__(self, root_key: str = MODELS_VOLUME) -> None:
        self._root_key = root_key
        self._lock = threading.RLock()
        # Lock order: _scanning, then _hashing, then _lock. Lookups and add/remove take only _lock.
        self._scanning = threading.Lock()  # serializes scan calls
        self._hashing = threading.Lock()  # serializes hash_pending calls
        self._records: dict[str, IndexRecord] = {}  # relative -> record
        self._queue: dict[Path, tuple[int, int]] = {}  # path -> (size, mtime_ns)
        self._progress: dict[Path, float] = {}
        self._lost_sources: dict[str, str] = {}  # sha256 -> source of dropped records
        self._listeners: list[Callable[[], None]] = []
        self._root: Path | None = None
        self._loaded = False
        self._touched: set[str] | None = None  # relatives changed by add/remove during a walk
        self.problem: str | None = None

    # -- listeners -------------------------------------------------------------

    def add_listener(self, cb: Callable[[], None]) -> None:
        """Call ``cb()`` after scan, hash completion, add and remove."""
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
                logger.exception("model index listener failed")

    # -- persistence -----------------------------------------------------------

    def _load(self, root: Path) -> None:
        self._loaded = True
        self._records = {}
        try:
            data = json.loads((root / INDEX_NAME).read_text(encoding="utf-8"))
            for item in data.get("files", []):
                rec = IndexRecord(**item)
                self._records[rec.relative] = rec
        except FileNotFoundError:
            pass
        except (OSError, ValueError, TypeError, AttributeError):
            logger.warning("unreadable model index at %s; rebuilding", root / INDEX_NAME)
            self._records = {}

    def _save(self) -> None:
        root = self._root
        if root is None or not root.is_dir():
            return
        payload = {"version": 1, "files": [asdict(r) for r in self._records.values()]}
        tmp = root / f"{INDEX_NAME}.tmp"
        try:
            tmp.write_text(json.dumps(payload, indent=1), encoding="utf-8")
            os.replace(tmp, root / INDEX_NAME)
        except OSError:
            logger.warning("could not write model index at %s", root, exc_info=True)

    # -- scan / hash -----------------------------------------------------------

    def scan(self) -> list[Path]:
        """Stat-walk the volume; return the paths queued for hashing.

        Concurrent calls run one after another.
        """
        with self._scanning:
            return self._scan()

    def _scan(self) -> list[Path]:
        try:
            root = location_of(self._root_key)
        except VolumeError as exc:
            return self._fail(str(exc))
        if not root.is_dir():
            return self._fail(f"volume location '{root}' does not exist")
        with self._lock:
            self.problem = None
            self._root = root
            if not self._loaded:
                self._load(root)
            self._touched = set()
        # The walk runs unlocked so lookups and adds never wait on the filesystem.
        found: dict[str, tuple[Path, int, int]] = {}
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            for name in filenames:
                if name.startswith(".") or name.endswith(_SKIP_SUFFIXES):
                    continue
                path = Path(dirpath) / name
                try:
                    st = path.stat()
                except OSError:
                    continue
                found[path.relative_to(root).as_posix()] = (path, st.st_size, st.st_mtime_ns)
        with self._lock:
            kept: dict[str, IndexRecord] = {}
            queue: dict[Path, tuple[int, int]] = {}
            for rel, (path, size, mtime) in found.items():
                old = self._records.get(rel)
                if old is not None and old.size == size and old.mtime_ns == mtime:
                    kept[rel] = old
                else:
                    queue[path] = (size, mtime)
            # add()/remove() during the walk win over what the walk saw: an added
            # record stays; a removed one is not resurrected (its file is re-queued).
            touched, self._touched = self._touched or set(), None
            for rel in touched:
                rec = self._records.get(rel)
                if rec is not None:
                    kept[rel] = rec
                    queue.pop(root / rel, None)
            for rel, rec in self._records.items():
                if rel not in kept and rec.source:
                    self._lost_sources[rec.sha256] = rec.source
            self._records = kept
            self._queue = queue
            # A file being hashed keeps its progress across a rescan.
            self._progress = {p: self._progress.get(p, 0.0) for p in queue}
            if not queue:
                self._save()
            queued = list(queue)
        self._notify()
        return queued

    def _fail(self, message: str) -> list[Path]:
        with self._lock:
            self.problem = message
            self._records = {}
            self._queue = {}
            self._progress = {}
            self._root = None
            self._loaded = False
            self._touched = None
        self._notify()
        return []

    def hash_pending(self, on_progress: Callable[[Path, int, int], None] | None = None) -> None:
        """Hash every queued file on the calling thread, then persist.

        Concurrent calls run one after another; a later call hashes only what is still queued.
        """
        with self._hashing:
            self._hash_pending(on_progress)

    def _hash_pending(self, on_progress: Callable[[Path, int, int], None] | None) -> None:
        with self._lock:
            root = self._root
            todo = list(self._queue.items())
        if root is None:
            return
        for path, (size, mtime) in todo:
            digest = self._hash_file(path, size, on_progress)
            with self._lock:
                self._queue.pop(path, None)
                self._progress.pop(path, None)
                if digest is None:
                    continue
                rel = path.relative_to(root).as_posix()
                source = self._lost_sources.pop(digest, None)
                self._records[rel] = IndexRecord(digest, rel, size, mtime, source)
        with self._lock:
            self._save()
        self._notify()

    def _hash_file(
        self, path: Path, size: int, on_progress: Callable[[Path, int, int], None] | None
    ) -> str | None:
        h = hashlib.sha256()
        done = 0
        try:
            with path.open("rb") as fh:
                while chunk := fh.read(_CHUNK):
                    h.update(chunk)
                    done += len(chunk)
                    with self._lock:
                        self._progress[path] = done / size if size else 1.0
                    if on_progress is not None:
                        on_progress(path, done, size)
        except OSError:
            return None
        return h.hexdigest()

    def pending(self) -> dict[Path, float]:
        """Queued files and the fraction hashed so far."""
        with self._lock:
            return dict(self._progress)

    # -- queries ---------------------------------------------------------------

    def _path_of(self, rec: IndexRecord) -> Path | None:
        return self._root / rec.relative if self._root is not None else None

    def by_sha256(self, sha: str) -> Path | None:
        with self._lock:
            for rec in self._records.values():
                if rec.sha256 == sha:
                    return self._path_of(rec)
        return None

    def by_source(self, uri: str) -> IndexRecord | None:
        with self._lock:
            for rec in self._records.values():
                if rec.source == uri:
                    return rec
        return None

    def sha256_at(self, path: Path) -> str | None:
        """Digest recorded for the file at ``path`` (feeds ``target_path``)."""
        with self._lock:
            if self._root is None:
                return None
            try:
                rel = path.relative_to(self._root).as_posix()
            except ValueError:
                return None
            rec = self._records.get(rel)
            return rec.sha256 if rec else None

    def records(self) -> list[IndexRecord]:
        with self._lock:
            return list(self._records.values())

    # -- mutation --------------------------------------------------------------

    def add(self, path: Path, sha256: str, source: str | None) -> None:
        """Record a file that is already hashed (a finished download)."""
        with self._lock:
            if self._root is None:
                try:
                    self._root = location_of(self._root_key)
                except VolumeError:
                    return
            if not self._loaded:
                self._load(self._root)
            try:
                rel = path.relative_to(self._root).as_posix()
                st = path.stat()
            except (ValueError, OSError):
                return
            self._records[rel] = IndexRecord(sha256, rel, st.st_size, st.st_mtime_ns, source)
            if self._touched is not None:
                self._touched.add(rel)
            self._save()
        self._notify()

    def remove(self, sha256: str) -> None:
        with self._lock:
            if self._touched is not None:
                self._touched.update(k for k, r in self._records.items() if r.sha256 == sha256)
            self._records = {k: r for k, r in self._records.items() if r.sha256 != sha256}
            self._save()
        self._notify()
