"""Resolving a :class:`~haywire.core.volumes.VolumePath` to a path on this machine; volume status."""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath

from haywire.core.volumes.keys import PROJECT_KEY
from haywire.core.volumes.store import VolumeStore, get_volume_store
from haywire.core.volumes.value import VolumePath

__all__ = [
    "VolumeError",
    "VolumeEscapeError",
    "VolumeStatus",
    "VolumeUndefinedError",
    "list_volumes",
    "location_of",
    "resolve",
]


class VolumeError(Exception):
    """Base class for volume resolution errors."""


class VolumeUndefinedError(VolumeError):
    """The volume has no location on this machine."""

    def __init__(self, volume: str) -> None:
        super().__init__(f"volume '{volume}' is not defined on this machine")
        self.volume = volume


class VolumeEscapeError(VolumeError):
    """A volume path resolves outside its volume."""

    def __init__(self, path: VolumePath, reason: str) -> None:
        super().__init__(f"{path} escapes its volume: {reason}")
        self.path = path
        self.reason = reason


def location_of(key: str, store: VolumeStore | None = None) -> Path:
    """Return the root of volume *key*; never creates it.

    The project volume is the open project's folder; every other volume's root is
    its location in the volumes file.

    Raises:
        VolumeUndefinedError: If there is no volume *key* on this machine, or *key*
            is the project volume and no project is open.
    """
    entry = (store if store is not None else get_volume_store()).entry(key)
    if entry is None or entry.location is None:
        raise VolumeUndefinedError(key)
    return entry.location


def resolve(path: VolumePath, store: VolumeStore | None = None) -> Path:
    """Return where *path* is on this machine: its volume's location joined with ``relative``.

    The location is used as configured, even when it is a symlink. A symlink inside
    the volume is followed only to check that it stays inside; the returned path
    keeps it. Never creates anything; the path need not exist.

    Raises:
        VolumeUndefinedError: If the volume has no location.
        VolumeEscapeError: If ``relative`` is not a string, contains a NUL byte or a
            ``..`` segment, is absolute, or resolves outside the volume (a symlink).
        VolumeError: If the path cannot be resolved (a symlink loop, an OS error).
    """
    root = location_of(path.volume, store)
    relative = path.relative
    if not isinstance(relative, str):
        raise VolumeEscapeError(path, f"relative path {relative!r} is not a string")
    if "\0" in relative:
        raise VolumeEscapeError(path, "relative path contains a NUL byte")
    if PurePosixPath(relative).is_absolute() or PureWindowsPath(relative).drive:
        raise VolumeEscapeError(path, f"{relative!r} is an absolute path")
    parts = PurePosixPath(relative).parts
    if ".." in parts:
        raise VolumeEscapeError(path, "'..' is not allowed in a volume path")
    target = root.joinpath(*parts)
    if not _has_symlink(root, parts):
        return target
    try:
        real_root = root.resolve()
        if target.resolve().is_relative_to(real_root):
            return target
        reason = _escape_reason(real_root, root, parts)
    except (OSError, RuntimeError) as exc:
        # Symlink loop: RuntimeError on Python 3.12, OSError from 3.13 on.
        raise VolumeError(f"{path} cannot be resolved: {exc}") from exc
    raise VolumeEscapeError(path, reason)


def _has_symlink(root: Path, parts: tuple[str, ...]) -> bool:
    """True if a component of ``root/parts`` below *root* is a symlink.

    Stops at the first component that cannot be read: what does not exist cannot be
    a link, and what cannot be looked at cannot be opened through either.
    """
    current = str(root)
    for part in parts:
        current = os.path.join(current, part)
        try:
            if stat.S_ISLNK(os.lstat(current).st_mode):
                return True
        except OSError:
            return False
    return False


def _escape_reason(real_root: Path, root: Path, parts: tuple[str, ...]) -> str:
    """Name the first component whose resolved prefix leaves the root."""
    current = root
    for index, part in enumerate(parts):
        current = current / part
        if not current.resolve().is_relative_to(real_root):
            prefix = "/".join(parts[: index + 1])
            if current.is_symlink():
                return f"'{prefix}' is a symlink pointing outside the volume"
            return f"'{prefix}' leads outside the volume"
    return "path leads outside the volume"


@dataclass(frozen=True)
class VolumeStatus:
    """A volume as people see it on this machine.

    ``location`` is ``None`` when it has none (the project volume with no project
    open); ``exists`` says whether the folder is there; ``editable`` is ``False``
    only for the project volume; ``suggested`` is the location a library volume
    resets to (see ``VolumeStore.reset``), ``None`` when there is none.
    """

    key: str
    label: str
    description: str
    location: Path | None
    exists: bool
    editable: bool
    suggested: Path | None = None


def list_volumes(store: VolumeStore | None = None) -> list[VolumeStatus]:
    """Return every volume: the project volume first, the rest sorted by label."""
    store = store if store is not None else get_volume_store()
    result: list[VolumeStatus] = []
    for entry in store.entries():
        try:
            exists = entry.location is not None and entry.location.exists()
        except OSError:
            exists = False
        result.append(
            VolumeStatus(
                key=entry.key,
                label=entry.label,
                description=entry.description,
                location=entry.location,
                exists=exists,
                editable=entry.key != PROJECT_KEY,
                suggested=entry.suggested,
            )
        )
    return result
