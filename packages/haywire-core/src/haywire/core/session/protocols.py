# packages/haywire-core/src/haywire/core/session/protocols.py
"""
Structural protocols for the Haywire UI system.

These protocols define the interface the framework expects from host application
objects, avoiding circular imports while providing full IDE type resolution.
"""

from __future__ import annotations

from typing import Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from haywire.core.di.config import LibrarySystemService
    from haywire.core.session.session_manager import SessionManager
    from haywire.core.state import LibraryStateContainer
    from haywire.core.node.registry import NodeRegistry
    from haywire.core.node.factory import NodeFactory
    from haywire.ui.panel.registry import PanelRegistry
    from haywire.ui.widget.factory import WidgetFactory


class IProjectState(Protocol):
    """
    Structural interface the framework expects from the host application.

    HaywireApp satisfies this protocol without inheriting from it.
    """

    workspace_root: str
    library_service: "LibrarySystemService"
    session_manager: "SessionManager"
    node_registry: "NodeRegistry"
    node_factory: "NodeFactory"
    panel_registry: "PanelRegistry"
    widget_factory: "WidgetFactory"
    library_state_container: "LibraryStateContainer"
    """Pool of live LibraryState instances."""
