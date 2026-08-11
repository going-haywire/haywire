# packages/haywire-core/src/haywire/core/library/info.py
"""
LibraryInfo — a library as the Library Manager sees it.

Pairs the library's declared metadata (a ``Haybale``, read from its own
``haybale.toml`` or taken from a marketstall row) with the install state
discovered during scanning. Built for catalogued-but-absent libraries too, so
the browser and the detail editor consume one type either way.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .identity import LibraryIdentity
from .install_type import InstallType

if TYPE_CHECKING:
    from .haybale import Haybale


@dataclass(frozen=True)
class LibraryInfo:
    """A library and, when it is installed here, its install state.

    The pip distribution name is ``row.name`` — canon, per ADR 0025. There is no
    separate field for it: the entry point's ``dist.name`` is a runtime echo of
    ``pyproject.toml``'s ``[project] name``, which is itself generated from
    ``haybale.toml``. Reading the echo would also lose folder installs, which
    have no entry point but do have a name (``builtin`` is ``haywire-core``).

    Attributes:
        row:          Declared metadata. The same shape whether it came from
                      the library's ``haybale.toml`` or from a feed.
        identity:     Runtime handles (``folder_path``, ``module_name``,
                      ``linked_libraries``). Empty when not installed.
        enabled:      Whether the library is currently enabled. ``False``
                      when not installed.
        install_type: How the library reached this environment, or
                      ``NOT_INSTALLED``.
    """

    row: "Haybale"
    identity: LibraryIdentity = field(default_factory=LibraryIdentity)
    enabled: bool = False
    install_type: InstallType = InstallType.NOT_INSTALLED

    @property
    def installed(self) -> bool:
        """Whether this library is present in this Python environment."""
        return self.install_type is not InstallType.NOT_INSTALLED
