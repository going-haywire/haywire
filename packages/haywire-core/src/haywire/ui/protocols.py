# packages/haywire-core/src/haywire/ui/protocols.py
"""
Structural protocols for the Haywire UI system.

These protocols define the interface the framework expects from host application
objects, avoiding circular imports while providing full IDE type resolution.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from haywire.core.di.config import LibrarySystemService
    from haywire.ui.session_manager import SessionManager
    from haywire_studio.library_manager import LibraryManager  # type: ignore[import-untyped]


class IGraphManager(Protocol):
    """
    Structural interface for graph file management.

    Haystack in haywire-studio satisfies this protocol without inheriting from it.
    Factory args are typed as Any to avoid importing the studio-specific GraphFactory
    type alias into haywire.ui.
    """

    def open_graph(self, path: Path, factory: Any) -> Any: ...
    def create_new(self, factory: Any) -> Any: ...
    def save_graph(self, entry: Any) -> None: ...


class IProjectState(Protocol):
    """
    Structural interface the framework expects from the host application.

    HaywireApp satisfies this protocol without inheriting from it.
    """

    library_service: "LibrarySystemService"
    workspace_root: str
    session_manager: "SessionManager"
    haystack: IGraphManager
    node_registry: Any  # NodeRegistry
    node_factory: Any  # NodeFactory
    library_manager: "LibraryManager"
