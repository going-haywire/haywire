"""
Core renderers (node renderers) registration and exports
"""

from haywire.core.registry.auto_discover import auto_discover_classes, is_renderer
from haywire.core.registry.base import LibraryMetadata
from haywire.core.registry.registry import RendererRegistry

# Import all renderer classes

def register_renderers(renderers_registry: RendererRegistry, library_metadata: LibraryMetadata):
    """Register all core node renderers with the renderers registry"""
    
    renderers = auto_discover_classes(
        library_path=__path__[0],
        class_filter=is_renderer
    )

    # Register all discovered renderers
    for renderer_class in renderers:
        renderers_registry.register_renderer(renderer_class, library_metadata)
    
__all__ = [
    'register_renderers'
]
