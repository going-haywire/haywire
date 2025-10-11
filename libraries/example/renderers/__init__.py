"""
Core renderers (node renderers) registration and exports
"""

from haywire.core.inventory.folder_scan import folder_scan_for_classes
from haywire.core.inventory.registry.renderer import RendererRegistry
from haywire.core.ui.renderer import is_renderer

# Import all renderer classes

def register_renderers(library):
    """Register all core node renderers with the renderers registry"""
    
    renderers = folder_scan_for_classes(
        library_path=__path__[0],
        metadata=library.metadata,
        class_filter=is_renderer
    )

    reg = library.get_registry(RendererRegistry)
    if reg:
        # Register all discovered renderers
        for renderer_class in renderers:
            reg.register_renderer(renderer_class, library.metadata)
    
__all__ = [
    'register_renderers'
]
