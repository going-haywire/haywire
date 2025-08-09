"""
Core renderers (node renderers) registration and exports
"""

from haywire.core.registry.registry import RendererRegistry

# Import all renderer classes
from .default_renderer import DefaultNodeRenderer
from .error_renderer import ErrorNodeRenderer


def register_renderers(renderers_registry: RendererRegistry):
    """Register all core node renderers with the renderers registry"""
    
    # Register default and error renderers
    renderers_registry.register_renderer('core.default', DefaultNodeRenderer)
    renderers_registry.register_renderer('core.error', ErrorNodeRenderer)

    # Set fallback renderers using class references
    renderers_registry.register_default_renderer('core.default')
    renderers_registry.register_error_renderer(ErrorNodeRenderer)

__all__ = [
    'DefaultNodeRenderer',
    'ErrorNodeRenderer',
    'register_renderers'
]
