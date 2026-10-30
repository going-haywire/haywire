"""The value a graph stores for a location inside a volume."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["VolumePath"]


@dataclass(frozen=True)
class VolumePath:
    """A location inside a named volume: ``(volume, relative)``.

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
        """Build from :meth:`to_dict` output; missing keys default to ``"project"`` and ``""``."""
        return cls(volume=data.get("volume", "project"), relative=data.get("relative", ""))

    def __str__(self) -> str:
        """Return ``"volume:relative"`` (display only; not parseable)."""
        return f"{self.volume}:{self.relative}"
