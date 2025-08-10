"""
Core renderers (node renderers) registration and exports
"""

from haywire.core.registry.registry_renderer import RendererRegistry
from haywire.core.registry.folder_scan import folder_scan_for_classes, is_renderer
from haywire.core.registry.registry_library import LibraryMetadata

# Import all renderer classes
from .default_renderer import DefaultNodeRenderer
from .error_renderer import ErrorNodeRenderer

def register_renderers(renderers_registry: RendererRegistry, library_metadata: LibraryMetadata):
    """Register all core node renderers with the renderers registry"""
    
    renderers = folder_scan_for_classes(
        library_path=__path__[0],
        class_filter=is_renderer
    )

    # Register all discovered renderers
    for renderer_class in renderers:
        renderers_registry.register_renderer(renderer_class, library_metadata)

    # Set fallback renderers using class references
    renderers_registry.register_default_renderer(DefaultNodeRenderer)
    renderers_registry.register_error_renderer(ErrorNodeRenderer)

__all__ = [
    'DefaultNodeRenderer',
    'ErrorNodeRenderer',
    'register_renderers'
]
