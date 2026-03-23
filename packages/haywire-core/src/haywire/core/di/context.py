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

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..node.factory import NodeFactory
    from ..adapter.factory import AdapterFactory
    from ..types.registry import TypeRegistry
    from ..settings import GlobalSettingsRegistry


_node_factory:      Optional['NodeFactory'] = None
_adapter_factory:   Optional['AdapterFactory'] = None
_type_registry:     Optional['TypeRegistry'] = None
_settings_registry: Optional['GlobalSettingsRegistry'] = None


# ---------------------------------------------------------------------------
# Setters — called by DI providers at startup
# ---------------------------------------------------------------------------

def set_node_factory(factory: 'NodeFactory') -> None:
    global _node_factory
    _node_factory = factory

def set_adapter_factory(factory: 'AdapterFactory') -> None:
    global _adapter_factory
    _adapter_factory = factory

def set_type_registry(registry: 'TypeRegistry') -> None:
    global _type_registry
    _type_registry = registry

def set_settings_registry(registry: 'GlobalSettingsRegistry') -> None:
    global _settings_registry
    _settings_registry = registry


# ---------------------------------------------------------------------------
# Getters — called by entity constructors
# ---------------------------------------------------------------------------

def get_node_factory() -> 'NodeFactory':
    if _node_factory is None:
        raise RuntimeError(
            "NodeFactory not set in ambient context. "
            "Ensure DI is initialised before constructing nodes."
        )
    return _node_factory

def get_adapter_factory() -> 'AdapterFactory':
    if _adapter_factory is None:
        raise RuntimeError(
            "AdapterFactory not set in ambient context. "
            "Ensure DI is initialised before constructing edges."
        )
    return _adapter_factory

def get_type_registry() -> 'TypeRegistry':
    if _type_registry is None:
        raise RuntimeError(
            "TypeRegistry not set in ambient context. "
            "Ensure DI is initialised before constructing nodes."
        )
    return _type_registry

def get_settings_registry() -> 'GlobalSettingsRegistry':
    if _settings_registry is None:
        raise RuntimeError(
            "GlobalSettingsRegistry not set in ambient context. "
            "Ensure DI is initialised before constructing nodes."
        )
    return _settings_registry
