from dataclasses import dataclass
from enum import StrEnum


class LibraryReloadAction(StrEnum):
    """What a library change (install, update, uninstall) demands of the user.

    Declared by the library author as ``on_reload`` in ``haybale.toml``. The
    three members form a ladder of escalating scope — each one is "hot-reload
    plus however much more this library needs":

    * ``NONE`` — hot-reload handles it; the user does nothing.
    * ``REFRESH`` — the library registers Vue components or JS resources an
      already-open browser tab cannot pick up; the tab must be reloaded.
    * ``RESTART`` — the Python process is left in a state hot-reload cannot
      repair (C-extension modules, import-time global mutation); the Studio
      must be restarted.

    Ordered, so combining declarations across libraries is ``max()``. The
    values are the lowercase member names, which is the form stored in TOML,
    in ``LibraryIdentity.on_reload`` and in farmhand JSON.
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

    Populated by ``@library(...)``: ``folder_path``, ``module_name`` and
    ``file_watcher`` from the call itself, the rest — including ``version`` and
    ``name`` — read out of ``haybale.toml``.

    Carries only the fields that cannot be read at the point of use:
    ``label``, ``linked_libraries`` and ``on_reload``. Everything descriptive
    is read from the file with ``read_haybale()`` when it is needed, so an edit
    is visible without a reload.
    """

    label: str = ""
    version: str = ""
    folder_path: str = ""  # Path to the library folder
    module_name: str = ""  # Python module name
    name: str = ""
    """The library's distribution (pip package) name, e.g. ``haybale-core``.
    Prefixes every component's registry key (``haybale-core:node:Add``) — the
    sole identifier"""
    linked_libraries: list[str] | None = None
    """Sibling haybales whose classes this library subscribes to, as *module*
    names (``haybale_studio``), not distribution names. Required for hot-reload
    scope tracking: without the declaration a subscriber holds a stale class
    reference after a reload."""
    file_watcher: bool = False  # Whether to watch for file changes
    on_reload: str = LibraryReloadAction.NONE.value
    """What the user must do after this library is installed, updated, or
    uninstalled. Stored in the wire form (``"none"``/``"refresh"``/``"restart"``)
    so it is identical on ``Haybale``, in TOML, and in farmhand JSON. Use
    :attr:`reload_action` to compare or combine declarations."""

    def __post_init__(self):
        if self.linked_libraries is None:
            self.linked_libraries = []
        # Normalise to the wire form: the enum or any case/whitespace variant
        # of its value is accepted, an unknown value raises here.
        self.on_reload = LibraryReloadAction(str(self.on_reload).strip().lower()).value

    @property
    def reload_action(self) -> LibraryReloadAction:
        """The ordered enum form of :attr:`on_reload`. Use for comparison and ``max()``."""
        return LibraryReloadAction(self.on_reload)
