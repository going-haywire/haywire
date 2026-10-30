"""The value a graph stores for a location inside a volume."""

from __future__ import annotations

from dataclasses import dataclass

from haywire.core.volumes.keys import PROJECT_KEY, volume_name

__all__ = ["VolumePath"]


@dataclass(frozen=True)
class VolumePath:
    """A location inside a volume: ``(volume, relative)``, where ``volume`` is the volume key.

    ``relative`` is a POSIX-style string (``/`` separators) kept verbatim; nothing
    in this class rewrites or validates it.
    """

    volume: str
    relative: str = ""

    def to_dict(self) -> dict[str, str]:
        """Return the serialized form ``{"volume", "relative"}``."""
        return {"volume": self.volume, "relative": self.relative}

    @classmethod
    def from_dict(cls, data: dict) -> VolumePath:
        """Build from :meth:`to_dict` output; a missing volume means the project volume."""
        return cls(volume=data.get("volume", PROJECT_KEY), relative=data.get("relative", ""))

    def __str__(self) -> str:
        """Return ``"<volume name>:<relative>"`` (display only; not parseable)."""
        return f"{volume_name(self.volume)}:{self.relative}"
