"""
InstallType enum for library installation classification.
"""

from enum import Enum


class InstallType(Enum):
    """Types of library installations.

    ``NOT_INSTALLED`` means the library is absent from this environment — a
    catalog row the user could install. It does **not** mean "was removed": an
    uninstall leaves no ``LibraryInfo`` at all.
    """

    REGULAR = "regular"  # Installed in site-packages
    EDITABLE = "editable"  # Installed with -e flag
    FOLDER = "folder"  # Discovered via folder scanning
    NOT_INSTALLED = "not_installed"  # Catalogued but absent from this environment

    def is_editable(self) -> bool:
        """True when a library's component source may be edited in place.

        THE single authority for "can I rewrite this component's source?" —
        used by both the source editor (read-only badge) and Farmhand's write
        tool. Only EDITABLE qualifies: a pip ``-e`` install whose ``__file__``
        still points at the developer's on-disk source, which the framework
        also hot-reloads. REGULAR (site-packages) is immutable; FOLDER is the
        framework-owned builtin library, not user-editable.
        """
        return self is InstallType.EDITABLE
