"""LevelMode — the three cumulative modes a session works a graph level in.

A StrEnum so the member is its wire string, like ``AccessTier``. Ordering is
expressed through :meth:`satisfies`: ``edit`` satisfies every check ``operate``
does, and ``operate`` every check ``view`` does.
"""

from __future__ import annotations

from enum import StrEnum


class LevelMode(StrEnum):
    """What a session may do on one graph level: look, change values, or change structure."""

    VIEW = "view"
    OPERATE = "operate"
    EDIT = "edit"

    @property
    def rank(self) -> int:
        """Position in the cumulative order — higher includes lower."""
        return _RANKS[self]

    def satisfies(self, required: "LevelMode") -> bool:
        """True when holding this mode is enough to meet ``required``."""
        return self.rank >= required.rank


_RANKS: dict[LevelMode, int] = {
    LevelMode.VIEW: 0,
    LevelMode.OPERATE: 1,
    LevelMode.EDIT: 2,
}
