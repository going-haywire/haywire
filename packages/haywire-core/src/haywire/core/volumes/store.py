"""The ``~/.haywire/volumes.toml`` file: the volumes on this machine and where each one lives."""

from __future__ import annotations

import logging
import os
import threading
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import tomlkit

from haywire.core.tomlio import plain, read_toml
from haywire.core.volumes.keys import (
    PROJECT_KEY,
    VOLUME_KEY_RE,
    is_user_volume_key,
    user_volume_key,
    volume_name,
)

logger = logging.getLogger(__name__)

__all__ = ["VolumeEntry", "VolumeStore", "ensure_volume", "get_volume_store", "set_volume_store"]


@dataclass(frozen=True)
class VolumeEntry:
    """One volume: its key, the label and description people see, and its location.

    ``location`` is ``None`` only for the project volume while no project is open.
    ``suggested`` is the location the volume's library suggests, ``None`` for a
    user volume and for a library volume whose library has not recorded one.
    """

    key: str
    label: str
    description: str
    location: Path | None
    suggested: Path | None = None


_PATH_LOCKS: dict[Path, threading.Lock] = {}
_PATH_LOCKS_GUARD = threading.Lock()


def _lock_for(path: Path) -> threading.Lock:
    with _PATH_LOCKS_GUARD:
        return _PATH_LOCKS.setdefault(path.absolute(), threading.Lock())


class _Unreadable(Exception):
    pass


class _UnreadableFileError(ValueError):
    pass


class VolumeStore:
    """Reads and writes the volumes file.

    Each ``[volumes."<key>"]`` table holds ``label``, ``description``, an
    absolute ``location`` and, for a library's volume, the absolute ``suggested``
    location its library gave. Only a user volume (``user:volume:<name>``) can be
    deleted; a library's volume is reset to its suggested location. The project
    volume (``PROJECT_KEY``) is built in: it is the open project's folder, never
    stored, and cannot be changed. An entry in the
    older ``[volumes] name = "/abs"`` form reads as the user volume ``name`` and is
    rewritten in the table form on the next write. Bad entries are logged and
    skipped; an unreadable file lists only the project volume and refuses writes.
    The file is re-read when its modification time or size changes. Writes are
    serialized per file and replace the file atomically.

    Example::

        store = VolumeStore(tmp_path / "volumes.toml")
        store.add("user:volume:scans", label="Scans", description="", location=Path("/Volumes/Scans"))
        store.update("user:volume:scans", label="Scanner drive")
        store.entry("user:volume:scans").location  # Path("/Volumes/Scans")
        store.remove("user:volume:scans")          # True

        # A library's volume: ensure records the suggestion, reset writes it back.
        store.ensure("haybale-models:volume:models", label="Models", description="", location=Path("/m"))
        store.update("haybale-models:volume:models", location=Path("/Volumes/Big/models"))
        store.reset("haybale-models:volume:models")  # Path("/m")
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path: Path = path if path is not None else Path.home() / ".haywire" / "volumes.toml"
        self._stamp: tuple[int, int] | None = None
        self._cache: dict[str, VolumeEntry] = {}

    # ------------------------------------------------------------------ reads

    def entries(self) -> list[VolumeEntry]:
        """Return the project volume, then every stored volume sorted by label."""
        stored = sorted(self._stored().values(), key=lambda e: (e.label.casefold(), e.key))
        return [_project_entry(), *stored]

    def entry(self, key: str) -> VolumeEntry | None:
        """Return the volume with *key*, or ``None`` if there is none."""
        if key == PROJECT_KEY:
            return _project_entry()
        return self._stored().get(key)

    def _stored(self) -> dict[str, VolumeEntry]:
        with _lock_for(self.path):
            try:
                st = self.path.stat()
            except OSError:
                self._stamp, self._cache = None, {}
                return {}
            stamp = (st.st_mtime_ns, st.st_size)
            if stamp != self._stamp:
                try:
                    self._cache = self._load()
                except _Unreadable as exc:
                    logger.error("Ignoring unreadable volumes file %s: %s", self.path, exc)
                    self._cache = {}
                self._stamp = stamp
            return dict(self._cache)

    def _load(self) -> dict[str, VolumeEntry]:
        """Parse the file; raise ``_Unreadable`` if it isn't TOML or ``volumes`` isn't a table."""
        return self._read_doc()[1]

    def _read_doc(self) -> tuple[Any, dict[str, VolumeEntry], dict[str, str]]:
        """Return the tomlkit document, its valid entries, and each entry's key as written in the file."""
        try:
            doc = read_toml(self.path)
        except Exception as exc:
            raise _Unreadable(str(exc)) from exc
        table = plain(doc).get("volumes", {})
        if not isinstance(table, dict):
            raise _Unreadable("[volumes] is not a table")
        entries: dict[str, VolumeEntry] = {}
        written_as: dict[str, str] = {}
        for raw_key, raw in table.items():
            entry = self._parse(raw_key, raw)
            if entry is not None:
                entries[entry.key] = entry
                written_as[entry.key] = raw_key
        return doc, entries, written_as

    def _parse(self, raw_key: str, raw: Any) -> VolumeEntry | None:
        label: Any
        description: Any
        location: Any
        suggested: Any = None
        if isinstance(raw, str):
            try:
                key = user_volume_key(raw_key)
            except ValueError:
                logger.warning("Ignoring volume %r in %s: invalid name", raw_key, self.path)
                return None
            label, description, location = raw_key, "", raw
        elif isinstance(raw, dict):
            key = raw_key
            if not VOLUME_KEY_RE.match(key):
                logger.warning("Ignoring volume %r in %s: invalid key", key, self.path)
                return None
            label = raw.get("label") or volume_name(key)
            description = raw.get("description", "")
            location = raw.get("location")
            suggested = raw.get("suggested")
        else:
            logger.warning("Ignoring volume %r in %s: not a table", raw_key, self.path)
            return None
        if key == PROJECT_KEY:
            logger.warning("Ignoring volume %r in %s: the project volume is built in", key, self.path)
            return None
        if not isinstance(location, str) or not Path(location).is_absolute():
            logger.warning("Ignoring volume %r in %s: location must be an absolute path", key, self.path)
            return None
        if not isinstance(label, str) or not isinstance(description, str):
            logger.warning("Ignoring volume %r in %s: label and description must be text", key, self.path)
            return None
        if suggested is not None and (not isinstance(suggested, str) or not Path(suggested).is_absolute()):
            logger.warning(
                "Ignoring the suggested location of volume %r in %s: not absolute", key, self.path
            )
            suggested = None
        return VolumeEntry(
            key, label, description, Path(location), Path(suggested) if suggested is not None else None
        )

    # ----------------------------------------------------------------- writes

    def add(self, key: str, *, label: str, description: str, location: Path) -> None:
        """Add a volume.

        Raises:
            ValueError: If *key* is invalid, is the project volume or already exists,
                if *location* is not absolute, or if the file is unreadable.
        """
        _check_key(key)
        _check_location(location)

        def apply(entries: dict[str, VolumeEntry]) -> bool:
            if key in entries:
                raise ValueError(f"A volume with key {key!r} already exists")
            entries[key] = VolumeEntry(key, label or volume_name(key), description, location)
            return True

        self._mutate(apply)

    def update(
        self,
        key: str,
        *,
        label: str | None = None,
        description: str | None = None,
        location: Path | None = None,
    ) -> None:
        """Change the given fields of volume *key*; the key itself never changes.

        Raises:
            ValueError: If *key* is the project volume or there is no volume *key*,
                if *location* is not absolute, or if the file is unreadable.
        """
        _check_writable(key)
        if location is not None:
            _check_location(location)

        def apply(entries: dict[str, VolumeEntry]) -> bool:
            current = entries.get(key)
            if current is None:
                raise ValueError(f"There is no volume {key!r}")
            changes: dict[str, Any] = {}
            if label is not None:
                changes["label"] = label or volume_name(key)
            if description is not None:
                changes["description"] = description
            if location is not None:
                changes["location"] = location
            entries[key] = replace(current, **changes)
            return True

        self._mutate(apply)

    def remove(self, key: str) -> bool:
        """Delete user volume *key*; return whether it existed.

        Raises:
            ValueError: If *key* is the project volume or a library's volume (see
                :meth:`reset`), or if the file is unreadable.
        """
        _check_writable(key)
        if not is_user_volume_key(key):
            raise ValueError(f"{key!r} is a library's volume: reset it to its suggested location instead")
        removed = False

        def apply(entries: dict[str, VolumeEntry]) -> bool:
            nonlocal removed
            removed = entries.pop(key, None) is not None
            return removed

        self._mutate(apply)
        return removed

    def reset(self, key: str) -> Path:
        """Set the location of library volume *key* back to its suggested location; return it.

        Label and description stay as they are. The folder is not created.

        Raises:
            ValueError: If *key* is the project volume or a user volume, there is no
                volume *key*, it has no suggested location, or the file is unreadable.
        """
        _check_writable(key)
        if is_user_volume_key(key):
            raise ValueError(f"{key!r} is a user volume: it has no suggested location")
        result: Path | None = None

        def apply(entries: dict[str, VolumeEntry]) -> bool:
            nonlocal result
            current = entries.get(key)
            if current is None:
                raise ValueError(f"There is no volume {key!r}")
            if current.suggested is None:
                raise ValueError(f"Volume {key!r} has no suggested location")
            result = current.suggested
            entries[key] = replace(current, location=current.suggested)
            return current.location != current.suggested

        self._mutate(apply)
        assert result is not None
        return result

    def ensure(self, key: str, *, label: str, description: str, location: Path) -> bool:
        """Add the volume unless *key* already exists; return whether it was added.

        *location* is also recorded as the volume's suggested location, also on an
        existing volume, so :meth:`reset` can write it back. Never changes an existing
        volume's label, description or location, and never creates *location*. An
        unreadable file, or one that cannot be written, is logged and left alone, and
        nothing is added.

        Raises:
            ValueError: If *key* is invalid or the project volume, or *location* is
                not absolute.
        """
        _check_key(key)
        _check_location(location)
        added = False

        def apply(entries: dict[str, VolumeEntry]) -> bool:
            nonlocal added
            current = entries.get(key)
            if current is not None:
                if current.suggested == location:
                    return False
                entries[key] = replace(current, suggested=location)
                return True
            entries[key] = VolumeEntry(key, label or volume_name(key), description, location, location)
            added = True
            return True

        try:
            self._mutate(apply)
        except (_UnreadableFileError, OSError) as exc:
            logger.error("Volume %r not added: %s", key, exc)
            return False
        return added

    def _mutate(self, apply: Callable[[dict[str, VolumeEntry]], bool]) -> None:
        """Re-read the file, let *apply* change the entries, and write back what changed.

        Only the changed volumes' tables are rewritten; comments, skipped entries and
        other tables stay as they are. Valid entries in the older ``name = "/abs"``
        form are rewritten as tables.
        """
        with _lock_for(self.path):
            if self.path.exists():
                try:
                    doc, entries, written_as = self._read_doc()
                except _Unreadable as exc:
                    raise _UnreadableFileError(f"The volumes file {self.path} is unreadable: {exc}") from exc
            else:
                doc, entries, written_as = tomlkit.document(), {}, {}
            before = dict(entries)
            if not apply(entries):
                return
            _sync(doc, before, entries, written_as)
            self._replace_file(tomlkit.dumps(doc))
            st = self.path.stat()
            self._stamp, self._cache = (st.st_mtime_ns, st.st_size), dict(entries)

    def _replace_file(self, text: str) -> None:
        """Write *text* to a temporary file next to the volumes file, then rename it over it."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_name(f"{self.path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        try:
            temp.write_text(text, encoding="utf-8")
            os.replace(temp, self.path)
        finally:
            temp.unlink(missing_ok=True)


def _sync(
    doc: Any, before: dict[str, VolumeEntry], after: dict[str, VolumeEntry], written_as: dict[str, str]
) -> None:
    """Bring the ``volumes`` table of *doc* from *before* to *after*, touching only what differs."""
    table = doc.get("volumes")
    if table is None:
        table = tomlkit.table(is_super_table=True)
        doc["volumes"] = table
    for key in before.keys() - after.keys():
        del table[written_as[key]]
    for key, entry in after.items():
        legacy = written_as.get(key, key) != key
        if before.get(key) == entry and not legacy:
            continue
        if legacy:
            del table[written_as[key]]
        assert entry.location is not None
        item = table[key] if key in table else tomlkit.table()
        item["label"] = entry.label
        item["description"] = entry.description
        item["location"] = str(entry.location)
        if entry.suggested is not None:
            item["suggested"] = str(entry.suggested)
        elif "suggested" in item:
            del item["suggested"]
        if key not in table:
            table[key] = item


def _project_entry() -> VolumeEntry:
    from haywire.core.di.context import get_workspace_root

    try:
        root: Path | None = get_workspace_root()
    except RuntimeError:
        root = None
    return VolumeEntry(PROJECT_KEY, "Project", "The open project's folder", root)


def _check_key(key: str) -> None:
    if key == PROJECT_KEY:
        raise ValueError("The project volume is built in and cannot be changed")
    if not VOLUME_KEY_RE.match(key):
        raise ValueError(f"Invalid volume key {key!r}: expected '<library>:volume:<name>'")


def _check_writable(key: str) -> None:
    if key == PROJECT_KEY:
        raise ValueError("The project volume is built in and cannot be changed")


def _check_location(location: Path) -> None:
    if not location.is_absolute():
        raise ValueError(f"Volume location must be absolute: {location}")


# --8<-- [start:ensure-volume]
def ensure_volume(
    key: str, *, label: str, description: str, location: Path, store: VolumeStore | None = None
) -> bool:
    """Add a library's volume unless it already exists; return whether it was added.

    Call it from the library's ``AppState.on_enable``. *location* is recorded as
    the volume's suggested location, which a reset writes back. It never changes a
    volume's label, description or location once the volume exists and never creates
    the folder, so it is safe on every enable and hot reload.

    Raises:
        ValueError: See :meth:`VolumeStore.ensure`.

    Example::

        class ModelsState(AppState):
            def on_enable(self) -> None:
                ensure_volume(
                    "haybale-models:volume:models",
                    label="Models",
                    description="Models on this machine",
                    location=Path.home() / ".haywire" / "db" / "haybale_models" / "models",
                )
    """
    target = store if store is not None else get_volume_store()
    return target.ensure(key, label=label, description=description, location=location)


# --8<-- [end:ensure-volume]


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
