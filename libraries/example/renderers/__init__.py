"""
Core renderers (node renderers) registration and exports
"""

from haywire.core.registry.base import LibraryMetadata
from haywire.core.registry.registry import RendererRegistry

# Import all renderer classes
from .example_renderer import ExampleNodeRenderer

def register_renderers(renderers_registry: RendererRegistry, library_metadata: LibraryMetadata):
    """Register all core node renderers with the renderers registry"""
    
    # Register default and error renderers
    renderers_registry.register_renderer('example.renderer', ExampleNodeRenderer)
    
__all__ = [
    'ExampleNodeRenderer',
    'register_renderers'
]
