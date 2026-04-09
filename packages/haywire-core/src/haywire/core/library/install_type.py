"""
InstallType enum for library installation classification.
"""

from enum import Enum


class InstallType(Enum):
    """Types of library installations"""

    REGULAR = "regular"  # Installed in site-packages
    EDITABLE = "editable"  # Installed with -e flag
    FOLDER = "folder"  # Discovered via folder scanning
