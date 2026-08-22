"""Graph file pre-hydration — bring an old ``.haywire`` dict to the current shape.

Runs at the top of ``BaseGraph.load_from_dict``, so every load path is
covered and the loader below it never grows ``if "old_key" in data``
branches.

Adding a format version: write ``vN.py`` with an :class:`Upgrader` whose
``_predecessor`` is ``vN-1``, then repoint :data:`_HEAD`.
"""

from __future__ import annotations

from haywire.core.errors.haywire_exception import HaywireException

from .upgrader import GraphDict, UnknownGraphFormat, Upgrader, UpgradeAncient
from .v1 import UpgradeVersionOne
from .v2 import UpgradeVersionTwo

#: Head of the chain — the newest version. Adding a version repoints this.
_HEAD: Upgrader = UpgradeVersionTwo()

#: Derived from the chain head, never written by hand, so the two cannot drift.
CURRENT_FORMAT_VERSION: int = _HEAD.to_version

__all__ = [
    "CURRENT_FORMAT_VERSION",
    "GraphDict",
    "UnknownGraphFormat",
    "UpgradeAncient",
    "UpgradeVersionOne",
    "UpgradeVersionTwo",
    "Upgrader",
    "prehydrate",
]


def prehydrate(data: GraphDict) -> GraphDict:
    """Upgrade a parsed graph dict to the current format, **in place**.

    The caller hands over ownership of *data*; upgraders mutate it.

    Two distinct failures, deliberately reported differently:

    - **From the future** — ``format_version`` exceeds what this Haywire
      supports. The only honest thing an older studio can say is "update
      Haywire": it cannot know what the newer shape looks like, so it must
      not guess.
    - **Not a graph** — no upgrader recognised it and it lacks the
      structural floor. A different problem with a different fix.

    The future-version check is **upfront, not in the except**: a v99 file
    that still has ``nodes`` and ``edges`` passes validation and would sail
    through the chain unchanged, silently half-loading a shape we cannot
    read. ``format_version`` is the one field whose meaning is guaranteed
    stable across versions, so it is the only thing testable before the
    chain touches anything.
    """
    found = data.get("format_version", 0)
    if found > CURRENT_FORMAT_VERSION:
        raise HaywireException.create(
            f"This graph was saved by a newer Haywire (file format v{found}; "
            f"this version supports up to v{CURRENT_FORMAT_VERSION}). "
            "Update Haywire to open it.",
            category="Graph Load Error",
        )

    try:
        return _HEAD.upgrade(data)
    except UnknownGraphFormat as exc:
        raise HaywireException.create(
            f"This file is not a recognisable Haywire graph ({exc}).",
            category="Graph Load Error",
        ) from exc
