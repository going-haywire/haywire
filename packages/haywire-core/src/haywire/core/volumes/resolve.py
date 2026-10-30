"""Resolving a :class:`~haywire.core.volumes.VolumePath` to a real path, and reporting volume status."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Literal

from haywire.core.volumes.store import VolumeStore, get_volume_store
from haywire.core.volumes.value import VolumePath
from haywire.core.volumes.volume import Volume, all_volumes, volume_by_name

logger = logging.getLogger(__name__)

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


def _default_of(declared: type[Volume]) -> Path | None:
    """Return *declared*'s default location, or ``None`` if it has none, raises, or is not absolute.

    A failing or relative default is logged, so one bad library declaration
    leaves only its own volume undefined.
    """
    try:
        location = declared.default()
    except Exception:
        logger.exception("Volume %r: default() raised; treating it as undefined", declared.name)
        return None
    if location is not None and not Path(location).is_absolute():
        logger.warning(
            "Volume %r: default() returned %r, which is not absolute; treating it as undefined",
            declared.name,
            str(location),
        )
        return None
    return location


def _locate(name: str, store: VolumeStore) -> tuple[Path | None, Literal["configured", "default", "fixed"]]:
    declared = volume_by_name(name)
    if declared is not None and not declared.configurable:
        return _default_of(declared), "fixed"
    configured = store.configured().get(name)
    if configured is not None:
        return configured, "configured"
    if declared is not None:
        return _default_of(declared), "default"
    return None, "default"


def location_of(name: str, store: VolumeStore | None = None) -> Path:
    """Return the root of volume *name*; never creates it.

    Order: non-configurable declared volume's default, then the ``volumes.toml``
    entry, then the declared default.

    A declared default that raises or is not absolute counts as none.

    Raises:
        VolumeUndefinedError: If none of these yields a location.
    """
    location, _ = _locate(name, store if store is not None else get_volume_store())
    if location is None:
        raise VolumeUndefinedError(name)
    return location


def resolve(path: VolumePath, store: VolumeStore | None = None) -> Path:
    """Return the absolute, symlink-resolved path for *path*; never creates anything.

    Raises:
        VolumeUndefinedError: If the volume has no location.
        VolumeEscapeError: If ``relative`` is not a string, contains a NUL byte,
            is absolute, or resolves outside the volume.
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
    try:
        target = root.joinpath(*parts).resolve()
        real_root = root.resolve()
        if target.is_relative_to(real_root):
            return target
        reason = _escape_reason(real_root, root, parts)
    except (OSError, RuntimeError) as exc:
        # Symlink loop: RuntimeError on Python 3.12, OSError from 3.13 on.
        raise VolumeError(f"{path} cannot be resolved: {exc}") from exc
    raise VolumeEscapeError(path, reason)


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
    """Where a volume stands on this machine."""

    name: str
    label: str
    description: str
    location: Path | None
    source: Literal["configured", "default", "fixed", "undefined"]
    exists: bool
    declared: bool
    configurable: bool


def list_volumes(store: VolumeStore | None = None) -> list[VolumeStatus]:
    """Return the status of every declared or configured volume.

    ``project`` and ``home`` come first, the rest sorted by name.
    """
    store = store if store is not None else get_volume_store()
    names = {v.name for v in all_volumes()} | set(store.configured())
    result: list[VolumeStatus] = []
    for name in names:
        declared = volume_by_name(name)
        location, source = _locate(name, store)
        result.append(
            VolumeStatus(
                name=name,
                label=declared.label if declared else name,
                description=declared.description if declared else "",
                location=location,
                source=source if location is not None else "undefined",
                exists=location is not None and location.exists(),
                declared=declared is not None,
                configurable=declared.configurable if declared else True,
            )
        )
    first = {"project": 0, "home": 1}
    result.sort(key=lambda s: (first.get(s.name, 2), s.name))
    return result
