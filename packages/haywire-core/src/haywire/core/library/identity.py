from dataclasses import dataclass
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


@dataclass
class LibraryIdentity:
    """Metadata for a Haywire library"""

    label: str
    version: str
    description: str
    url: str
    help_url: str
    author: str
    author_url: str
    folder_path: str  # Path to the library folder
    module_name: str  # Python module name
    id: str  # Unique identifier for the library
    dependencies: list[str] | None = None
    """Referenced haywire libraries (Python package names). Must be specified for
        hot-reload: this includes any library whose subclasses this one
        subscribes to — without the dependency, hot-reload
        leaves the subscriber holding a stale class reference"""
    tags: list[str] | None = None  # Searchable tags for marketplace/discovery
    file_watcher: bool = False  # Whether to watch for file changes
    on_reload: LibraryReloadAction = LibraryReloadAction.NONE
    """What the user must do after this library is installed, updated, or
        uninstalled — see :class:`LibraryReloadAction`. Symmetric: the same
        declaration applies in every direction, because what cannot be
        hot-swapped in also cannot be hot-swapped out. Accepts the bare string
        (``on_reload="restart"``), which is the on-disk form."""

    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []
        if self.tags is None:
            self.tags = []
        # Coerce the on-disk/string form. Authors write on_reload="restart" so
        # the decorator source needs no import of this enum; the marketplace
        # edit dialog and farmhand payloads pass plain strings for the same
        # reason.
        if not isinstance(self.on_reload, LibraryReloadAction):
            self.on_reload = LibraryReloadAction(str(self.on_reload).strip().lower())
