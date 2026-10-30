"""Volume declarations: named roots a :class:`~haywire.core.volumes.VolumePath` resolves against."""

from __future__ import annotations

import re
from abc import ABC
from pathlib import Path
from typing import Any, ClassVar

from haywire.core.di.context import get_workspace_root

__all__ = [
    "VOLUME_NAME_RE",
    "HomeVolume",
    "ProjectVolume",
    "Volume",
    "all_volumes",
    "volume_by_name",
]

VOLUME_NAME_RE = re.compile(r"^[a-z][a-z0-9_-]*$")

_VOLUME_BY_NAME: dict[str, type[Volume]] = {}


class Volume(ABC):
    """A declared volume.

    Subclass and set ``name`` (matching ``^[a-z][a-z0-9_-]*$``) and ``label`` to
    register it on import. Declaring a name already held by a class from another
    module or qualname raises ``ValueError``; re-declaring the same module and
    qualname (hot reload) replaces the earlier class.
    """

    name: ClassVar[str]
    label: ClassVar[str]
    description: ClassVar[str] = ""
    configurable: ClassVar[bool] = True
    """Whether ``volumes.toml`` may override :meth:`default`."""

    @classmethod
    def default(cls) -> Path | None:
        """Return the location used when ``volumes.toml`` has no entry, or ``None`` for none."""
        return None

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # Intermediate classes that don't declare a name are not registered.
        if "name" not in cls.__dict__:
            return
        name = cls.__dict__["name"]
        if not isinstance(name, str) or not VOLUME_NAME_RE.match(name):
            raise ValueError(f"Invalid volume name {name!r} on {cls.__module__}.{cls.__qualname__}")
        existing = _VOLUME_BY_NAME.get(name)
        if existing is not None:
            same_origin = existing.__module__ == cls.__module__ and existing.__qualname__ == cls.__qualname__
            if not same_origin:
                raise ValueError(
                    f"Volume name collision: {cls.__module__}.{cls.__qualname__} and "
                    f"{existing.__module__}.{existing.__qualname__} both declare name={name!r}"
                )
        _VOLUME_BY_NAME[name] = cls


def volume_by_name(name: str) -> type[Volume] | None:
    """Return the declared volume called *name*, or ``None``."""
    return _VOLUME_BY_NAME.get(name)


def all_volumes() -> list[type[Volume]]:
    """Return every declared volume, in declaration order."""
    return list(_VOLUME_BY_NAME.values())


# --8<-- [start:project-volume]
class ProjectVolume(Volume):
    """The current project's workspace root. Follows project switches."""

    name = "project"
    label = "Project"
    description = "The current project's workspace root."
    configurable = False

    @classmethod
    def default(cls) -> Path | None:
        """Return the ambient workspace root as of this call, or ``None`` if none is set."""
        try:
            return get_workspace_root()
        except RuntimeError:
            return None


# --8<-- [end:project-volume]


class HomeVolume(Volume):
    """The user's home folder."""

    name = "home"
    label = "Home"
    description = "The user's home folder."

    @classmethod
    def default(cls) -> Path | None:
        """Return the user's home folder."""
        return Path.home()
