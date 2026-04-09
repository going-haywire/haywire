# packages/haywire-core/src/haywire/core/library/info.py
"""
LibraryInfo — composed runtime snapshot for an installed library.

Combines the library's declared identity with runtime state discovered
during scanning: enabled status, install type, and pip distribution name.
"""

from dataclasses import dataclass

from .identity import LibraryIdentity
from .discovery import InstallType


@dataclass(frozen=True)
class LibraryInfo:
    """Runtime snapshot of an installed library.

    Attributes:
        identity:          Declared metadata from the @library decorator.
        enabled:           Whether the library is currently enabled.
        install_type:      How the library was installed (REGULAR, EDITABLE, FOLDER).
        distribution_name: Pip package name, e.g. 'haybale-visiongraph'. Empty string
                           if installed as a folder (no pip distribution).
    """

    identity: LibraryIdentity
    enabled: bool
    install_type: InstallType
    distribution_name: str
