# haywire/ui/protocols.py
"""
Structural protocols for the Haywire UI system.

These protocols define the interface the framework expects from host application
objects, avoiding circular imports while providing full IDE type resolution.
"""

from typing import Protocol

from haywire.core.di.config import LibrarySystemService


class IProjectState(Protocol):
    """
    Structural interface the framework expects from the host application.

    HaywireApp satisfies this protocol without inheriting from it.
    Any attribute not listed here is accessible as Any via context.app.
    """

    library_service: LibrarySystemService
    workspace_root: str
