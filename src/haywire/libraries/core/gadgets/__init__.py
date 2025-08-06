"""
Core gadgets (node renderers) registration and exports
"""

from haywire.core.registry.registry import GadgetsRegistry

# Import all renderer classes
from .default import DefaultNodeRenderer
from .error import ErrorNodeRenderer


def register_core_gadgets(gadgets_registry: GadgetsRegistry):
    """Register all core node renderers with the gadgets registry"""
    
    # Register default and error renderers
    gadgets_registry.register_renderer('default', DefaultNodeRenderer)
    
    # Set fallback renderers using class references
    gadgets_registry.register_default_renderer(DefaultNodeRenderer)
    gadgets_registry.register_error_renderer(ErrorNodeRenderer)


__all__ = [
    'DefaultNodeRenderer',
    'ErrorNodeRenderer',
    'register_core_gadgets'
]
