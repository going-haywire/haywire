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
    on_reload: str = LibraryReloadAction.NONE.value
    """What the user must do after this library is installed, updated, or
        uninstalled. Stored in the wire form (``"none"``/``"refresh"``/``"restart"``)
        so it is identical on ``Haybale``, in TOML, and in farmhand JSON. Use
        :attr:`reload_action` to compare or combine declarations."""

    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []
        if self.tags is None:
            self.tags = []
        # Validate and normalise to the wire form. Accepts the enum or any
        # case/whitespace variant of its value; an unknown value raises here
        # rather than at the next library import.
        self.on_reload = LibraryReloadAction(str(self.on_reload).strip().lower()).value

    @property
    def reload_action(self) -> LibraryReloadAction:
        """The ordered enum form. Use for comparison and ``max()``; the stored
        field is a plain string so both metadata shapes agree."""
        return LibraryReloadAction(self.on_reload)
