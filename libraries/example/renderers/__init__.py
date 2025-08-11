"""
Core renderers (node renderers) registration and exports
"""

from haywire.core.inventory.folder_scan import folder_scan_for_classes
from haywire.core.inventory.base import LibraryMetadata
from haywire.core.inventory.registry.renderer import RendererRegistry
from haywire.core.ui.renderer import is_renderer

# Import all renderer classes

def register_renderers(renderers_registry: RendererRegistry, library_metadata: LibraryMetadata):
    """Register all core node renderers with the renderers registry"""
    
    renderers = folder_scan_for_classes(
        library_path=__path__[0],
        class_filter=is_renderer
    )

    # Register all discovered renderers
    for renderer_class in renderers:
        renderers_registry.register_renderer(renderer_class, library_metadata)
    
__all__ = [
    'register_renderers'
]
