# haywire/core/di/context.py
"""
Ambient context for app-scoped singletons.

Set once at startup by HaywireModule providers; read by deep entity constructors
(BaseNode, NodeWrapper, EdgeWrapper) that cannot receive these via constructor
injection without polluting unrelated intermediaries.

Usage
-----
Read (in entity constructors):
    from haywire.core.di.context import get_node_factory
    self._node_factory = get_node_factory()

Write (in DI providers only):
    from haywire.core.di.context import set_node_factory
    set_node_factory(factory)
"""

from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..node.factory import NodeFactory
    from ..adapter.factory import AdapterFactory
    from ..types.registry import TypeRegistry
    from ..settings import GlobalSettingsRegistry


_node_factory:      ContextVar = ContextVar('node_factory')
_adapter_factory:   ContextVar = ContextVar('adapter_factory')
_type_registry:     ContextVar = ContextVar('type_registry')
_settings_registry: ContextVar = ContextVar('settings_registry')


# ---------------------------------------------------------------------------
# Setters — called by DI providers at startup
# ---------------------------------------------------------------------------

def set_node_factory(factory: 'NodeFactory') -> None:
    _node_factory.set(factory)

def set_adapter_factory(factory: 'AdapterFactory') -> None:
    _adapter_factory.set(factory)

def set_type_registry(registry: 'TypeRegistry') -> None:
    _type_registry.set(registry)

def set_settings_registry(registry: 'GlobalSettingsRegistry') -> None:
    _settings_registry.set(registry)


# ---------------------------------------------------------------------------
# Getters — called by entity constructors
# ---------------------------------------------------------------------------

def get_node_factory() -> 'NodeFactory':
    try:
        return _node_factory.get()
    except LookupError:
        raise RuntimeError("NodeFactory not set in ambient context. Ensure DI is initialised before constructing nodes.")

def get_adapter_factory() -> 'AdapterFactory':
    try:
        return _adapter_factory.get()
    except LookupError:
        raise RuntimeError("AdapterFactory not set in ambient context. Ensure DI is initialised before constructing edges.")

def get_type_registry() -> 'TypeRegistry':
    try:
        return _type_registry.get()
    except LookupError:
        raise RuntimeError("TypeRegistry not set in ambient context. Ensure DI is initialised before constructing nodes.")

def get_settings_registry() -> 'GlobalSettingsRegistry':
    try:
        return _settings_registry.get()
    except LookupError:
        raise RuntimeError("GlobalSettingsRegistry not set in ambient context. Ensure DI is initialised before constructing nodes.")
