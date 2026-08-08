"""A library as loaded in this process.

``LibraryReloadAction`` moved to :mod:`haywire.core.library.reload` so
:mod:`haywire.core.library.metadata` can import it without a cycle; it is
re-exported here because several call sites import it from this module.
"""

from dataclasses import dataclass

from haywire.core.library.metadata import LibraryMetadata
from haywire.core.library.reload import LibraryReloadAction

__all__ = ["LibraryIdentity", "LibraryMetadata", "LibraryReloadAction"]


@dataclass
class LibraryIdentity(LibraryMetadata):
    """A library as loaded in this process.

    Adds the live wiring — registry key, on-disk location, watch flag — to the
    metadata every shape carries.
    """

    id: str = ""
    """Unique identifier within the studio; prefixes every component's registry key."""

    folder_path: str = ""
    """Path to the library's module directory. Set by the decorator."""

    module_name: str = ""
    """Python module name. Set by the decorator."""

    file_watcher: bool = False
    """Watch this library's files and hot-reload on change. Development only."""

    def __post_init__(self):
        # Validate and normalise to the wire form. Accepts the enum or any
        # case/whitespace variant of its value; an unknown value raises here
        # rather than at the next library import.
        self.on_reload = LibraryReloadAction(str(self.on_reload).strip().lower()).value
