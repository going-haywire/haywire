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
    """A library as loaded in this process.

    Populated by ``@library(...)``: ``id``, ``folder_path``, ``module_name`` and
    ``file_watcher`` from the call itself, ``version`` from the installed
    distribution, and the rest read out of ``haybale.toml``.

    The descriptive fields below (``description``, ``url``, ``author``,
    ``author_url``, ``tags``) are **transitional**. The design has consumers read
    them from ``haybale.toml`` at the point of use instead, so an edit is visible
    without a reload; they are still carried here while ~30 call sites are
    migrated. What must stay on the identity is only what cannot do a file read:
    ``label`` (logged and rendered from inside the registry), ``linked_libraries``
    (read during module registration, inside the import machinery), and
    ``on_reload`` (read by ``_hints_for_library`` *after* a library is evicted,
    when its files may already be gone).
    """

    label: str = ""
    version: str = ""
    description: str = ""
    url: str = ""
    author: str = ""
    author_url: str = ""
    folder_path: str = ""  # Path to the library folder
    module_name: str = ""  # Python module name
    id: str = ""  # Unique identifier for the library
    linked_libraries: list[str] | None = None
    """Sibling haybales whose classes this library subscribes to, as **module**
    names (``haybale_studio``). Required for hot-reload scope tracking: without
    the declaration a subscriber holds a stale class reference after a reload.

    Renamed from ``dependencies``, which collided with ``[project]
    dependencies`` — pip requirements, a different concept entirely."""
    tags: list[str] | None = None  # Searchable tags for marketplace/discovery
    file_watcher: bool = False  # Whether to watch for file changes
    on_reload: str = LibraryReloadAction.NONE.value
    """What the user must do after this library is installed, updated, or
        uninstalled. Stored in the wire form (``"none"``/``"refresh"``/``"restart"``)
        so it is identical on ``Haybale``, in TOML, and in farmhand JSON. Use
        :attr:`reload_action` to compare or combine declarations."""

    def __post_init__(self):
        if self.linked_libraries is None:
            self.linked_libraries = []
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
