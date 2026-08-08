"""What a library change demands of the user after install, update, or uninstall.

Lives apart from identity.py so LibraryMetadata can import it without a cycle.
"""

from enum import StrEnum


class LibraryReloadAction(StrEnum):
    """What a library change (install, update, uninstall) demands of the user.

    Declared by the library author via ``@library(on_reload=...)``. The three
    members form a ladder of escalating scope — each one is "hot-reload plus
    however much more this library needs":

    * ``NONE`` — hot-reload handles it; the user does nothing.
    * ``REFRESH`` — the library registers Vue components or JS resources an
      already-open browser tab cannot pick up; the tab must be reloaded.
    * ``RESTART`` — the Python process is left in a state hot-reload cannot
      repair (C-extension modules, import-time global mutation); the Studio
      must be restarted.

    Ordered, so combining declarations across libraries is ``max()``. Values
    are lowercase strings so the member round-trips through the decorator
    source, the marketplace edit dialog's identity dict, and farmhand JSON
    without any of them needing to import this enum.
    """

    NONE = "none"
    REFRESH = "refresh"
    RESTART = "restart"

    @property
    def _rank(self) -> int:
        return _RELOAD_ACTION_RANK[self]

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, LibraryReloadAction):
            return NotImplemented
        return self._rank < other._rank

    def __le__(self, other: object) -> bool:
        if not isinstance(other, LibraryReloadAction):
            return NotImplemented
        return self._rank <= other._rank

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, LibraryReloadAction):
            return NotImplemented
        return self._rank > other._rank

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, LibraryReloadAction):
            return NotImplemented
        return self._rank >= other._rank


#: Escalation order. Defined outside the class so it is not mistaken for a
#: member; StrEnum would otherwise treat a dict attribute as one.
_RELOAD_ACTION_RANK = {
    LibraryReloadAction.NONE: 0,
    LibraryReloadAction.REFRESH: 1,
    LibraryReloadAction.RESTART: 2,
}
