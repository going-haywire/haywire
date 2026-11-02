"""The value a graph stores for a location inside a volume."""

from __future__ import annotations

from dataclasses import dataclass, field

from haywire.core.volumes.keys import PROJECT_KEY, volume_name

__all__ = ["VolumePath"]


@dataclass(frozen=True)
class VolumePath:
    """A location inside a volume: ``(volume, relative)``, where ``volume`` is the volume key.

    ``relative`` is a POSIX-style string (``/`` separators) kept verbatim; nothing
    in this class rewrites or validates it.

    ``base`` optionally marks the folder a listing started from, a leading part of
    ``relative`` such as ``assets/in`` for ``assets/in/sub/c.png``. It does not take
    part in equality or hashing: two paths to the same file are equal whatever
    their base. See :attr:`subpath`.

    Example::

        listed = VolumePath(PROJECT_KEY, "assets/in/sub/c.png", base="assets/in")
        listed.subpath                                    # "sub/c.png"
        listed == VolumePath(PROJECT_KEY, "assets/in/sub/c.png")  # True
    """

    volume: str
    relative: str = ""
    base: str = field(default="", compare=False)

    @property
    def subpath(self) -> str:
        """Return the part of ``relative`` below ``base``.

        All of ``relative`` when ``base`` is empty or not a leading part of it.
        """
        base = self.base.strip("/")
        if not base:
            return self.relative
        if self.relative == base:
            return ""
        if self.relative.startswith(base + "/"):
            return self.relative[len(base) + 1 :]
        return self.relative

    def to_dict(self) -> dict[str, str]:
        """Return the serialized form ``{"volume", "relative"}``, plus ``"base"`` when one is set."""
        data = {"volume": self.volume, "relative": self.relative}
        if self.base:
            data["base"] = self.base
        return data

    @classmethod
    def from_dict(cls, data: dict) -> VolumePath:
        """Build from :meth:`to_dict` output; a missing volume means the project volume."""
        return cls(
            volume=data.get("volume", PROJECT_KEY),
            relative=data.get("relative", ""),
            base=data.get("base", ""),
        )

    def __str__(self) -> str:
        """Return ``"<volume name>:<relative>"`` (display only; not parseable)."""
        return f"{volume_name(self.volume)}:{self.relative}"
