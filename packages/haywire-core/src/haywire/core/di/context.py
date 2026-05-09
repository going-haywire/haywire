# haywire/core/di/context.py
"""
Ambient context for app-scoped singletons.

Set once at startup by HaywireModule providers; read by deep entity constructors
(BaseNode, NodeWrapper, EdgeWrapper) that cannot receive these via constructor
injection without polluting unrelated intermediaries.

Uses module-level globals (not ContextVar) because these are true app-wide
singletons that must be accessible from any thread — including the watchdog
file-watcher thread used for hot-reload.

Usage
-----
Read (in entity constructors):
    from haywire.core.di.context import get_node_factory
    self._node_factory = get_node_factory()

Write (in DI providers only):
    from haywire.core.di.context import set_node_factory
    set_node_factory(factory)
"""

from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..node.factory import NodeFactory
    from ..adapter.factory import AdapterFactory
    from ..types.registry import TypeRegistry
    from ..settings import SettingsRegistry
    from ..session.session_manager import SessionManager
    from ..state import LibraryStateContainer


_node_factory: Optional["NodeFactory"] = None
_adapter_factory: Optional["AdapterFactory"] = None
_type_registry: Optional["TypeRegistry"] = None
_settings_registry: Optional["SettingsRegistry"] = None
_session_manager: Optional["SessionManager"] = None
_workspace_root: Optional[Path] = None
_library_state_container: Optional["LibraryStateContainer"] = None


# ---------------------------------------------------------------------------
# Setters — called by DI providers at startup
# ---------------------------------------------------------------------------


def set_node_factory(factory: "NodeFactory") -> None:
    global _node_factory
    _node_factory = factory


def set_adapter_factory(factory: "AdapterFactory") -> None:
    global _adapter_factory
    _adapter_factory = factory


def set_type_registry(registry: "TypeRegistry") -> None:
    global _type_registry
    _type_registry = registry


def set_settings_registry(registry: "SettingsRegistry") -> None:
    global _settings_registry
    _settings_registry = registry


def set_session_manager(manager: "SessionManager") -> None:
    global _session_manager
    _session_manager = manager


def set_workspace_root(path) -> None:
    """Set the ambient workspace root. Accepts str or Path."""
    global _workspace_root
    _workspace_root = Path(path)


def set_library_state_container(container: "LibraryStateContainer") -> None:
    global _library_state_container
    _library_state_container = container


# ---------------------------------------------------------------------------
# Getters — called by entity constructors
# ---------------------------------------------------------------------------


def get_node_factory() -> "NodeFactory":
    if _node_factory is None:
        raise RuntimeError(
            "NodeFactory not set in ambient context. Ensure DI is initialised before constructing nodes."
        )
    return _node_factory


def get_adapter_factory() -> "AdapterFactory":
    if _adapter_factory is None:
        raise RuntimeError(
            "AdapterFactory not set in ambient context. Ensure DI is initialised before constructing edges."
        )
    return _adapter_factory


def get_type_registry() -> "TypeRegistry":
    if _type_registry is None:
        raise RuntimeError(
            "TypeRegistry not set in ambient context. Ensure DI is initialised before constructing nodes."
        )
    return _type_registry


def get_settings_registry() -> "SettingsRegistry":
    if _settings_registry is None:
        raise RuntimeError(
            "SettingsRegistry not set in ambient context. "
            "Ensure DI is initialised before constructing nodes."
        )
    return _settings_registry


def get_session_manager() -> "SessionManager":
    if _session_manager is None:
        raise RuntimeError(
            "SessionManager not set in ambient context. "
            "Ensure HaywireApp has been initialised before requesting it."
        )
    return _session_manager


def get_workspace_root() -> Path:
    if _workspace_root is None:
        raise RuntimeError(
            "workspace_root not set in ambient context. "
            "Ensure HaywireApp has been initialised before requesting it."
        )
    return _workspace_root


def get_library_state_container() -> "LibraryStateContainer":
    if _library_state_container is None:
        raise RuntimeError(
            "LibraryStateContainer not set in ambient context. "
            "Ensure HaywireApp has been initialised before requesting it."
        )
    return _library_state_container
