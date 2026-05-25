# packages/haywire-core/src/haywire/core/session/protocols.py
"""
Structural protocols for the Haywire UI system.

These protocols define the interface the framework expects from host application
objects, avoiding circular imports while providing full IDE type resolution.
"""

from __future__ import annotations

from typing import Any, Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from haywire.core.di.config import LibrarySystemService
    from haywire.core.session.session_manager import SessionManager
    from haywire.core.state import LibraryStateContainer


class IProjectState(Protocol):
    """
    Structural interface the framework expects from the host application.

    HaywireApp satisfies this protocol without inheriting from it.
    """

    library_service: "LibrarySystemService"
    workspace_root: str
    session_manager: "SessionManager"
    node_registry: Any  # NodeRegistry
    node_factory: Any  # NodeFactory
    library_state_container: "LibraryStateContainer"
    """Pool of live LibraryState instances.

    See docs/architecture/session-and-state/session-and-state-arch.md."""
    panel_registry: Any  # PanelRegistry — set by HaywireApp.setup_shared_services()
