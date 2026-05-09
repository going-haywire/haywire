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
    from haywire.core.state import LibraryStateContainer


class IGraphManager(Protocol):
    """
    Structural interface for graph file management.

    Haystack in haywire-studio satisfies this protocol without inheriting from it.
    Factory args are typed as Any to avoid importing the studio-specific GraphFactory
    type alias into haywire.ui.
    """

    def open_graph(self, path: Path) -> Any: ...
    def create_new(self) -> Any: ...
    def save_graph(self, entry: Any, save_as: Any = None) -> bool: ...
    def remove_entry(self, entry: Any) -> bool: ...
    def all_entries(self) -> Any: ...
    def unsaved_entries(self) -> Any: ...
    def list_haystacks(self) -> Any: ...
    def list_graph_files(self) -> Any: ...


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
    library_state_container: "LibraryStateContainer"
    """Pool of live LibraryState instances. See internals/documentation/architecture/library_state.md."""
