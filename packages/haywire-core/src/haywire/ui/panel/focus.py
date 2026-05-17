# packages/haywire-core/src/haywire/ui/panel/focus.py
"""Focus: a class hierarchy that discriminates which Panels apply to current state.

Each Focus subclass declares:
  - id: ClassVar[str]   — short stable identifier (used by DOM attributes
                          for context-menu triggers and by registry lookup).
  - label: ClassVar[str] — human-readable, used in toolbar chrome.
  - icon: ClassVar[str]  — Material Symbols icon name.
  - order: ClassVar[int] — sort priority in toolbars (lower = earlier).
  - available(cls, ctx) -> bool — classmethod returning whether this focus
                                  is reachable given current state.

The framework auto-builds an id → class map at class-definition time via
__init_subclass__. Collisions raise ValueError immediately.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from haywire.core.session.context import SessionContext

# id → Focus subclass map. Populated by Focus.__init_subclass__.
_FOCUS_BY_ID: dict[str, type["Focus"]] = {}


class Focus(ABC):
    """Discriminator for which Panels apply to current session state."""

    id: ClassVar[str]
    label: ClassVar[str]
    icon: ClassVar[str]
    order: ClassVar[int] = 100

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # Skip subclasses that don't declare id (intermediate ABCs).
        if "id" not in cls.__dict__:
            return
        focus_id = cls.__dict__["id"]
        if focus_id in _FOCUS_BY_ID:
            existing = _FOCUS_BY_ID[focus_id]
            same_origin = existing.__module__ == cls.__module__ and existing.__qualname__ == cls.__qualname__
            if not same_origin:
                raise ValueError(
                    f"Focus id collision: {cls.__module__}.{cls.__name__} and "
                    f"{existing.__module__}.{existing.__name__} both declare id={focus_id!r}"
                )
            # Same module + qualname: this is a hot-reload re-declaring its own
            # class. The new class object supersedes the old in _FOCUS_BY_ID.
        _FOCUS_BY_ID[focus_id] = cls

    @classmethod
    @abstractmethod
    def available(cls, ctx: Any) -> bool:
        """Return True if this Focus is reachable given current state.

        Implementations typically read one or more reactive fields off ctx.
        """


def focus_by_id(focus_id: str) -> type[Focus] | None:
    """Return the Focus subclass whose id matches focus_id, or None."""
    return _FOCUS_BY_ID.get(focus_id)


def all_focuses() -> list[type[Focus]]:
    """Return all registered Focus subclasses."""
    return list(_FOCUS_BY_ID.values())


class CanvasFocus(Focus):
    id = "canvas"
    label = "Canvas & Nodes"
    icon = "grid_on"
    order = 30

    @classmethod
    def available(cls, ctx: SessionContext) -> bool:
        return True
