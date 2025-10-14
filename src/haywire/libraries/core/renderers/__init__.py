"""
Core renderers (node renderers) registration and exports
"""

from haywire.core.inventory.library import BaseLibrary
from haywire.core.inventory.registry.renderer_reg import RendererRegistry
from haywire.core.inventory.folder_scan_for_classes import folder_scan_for_classes
from haywire.core.ui.base_renderer import is_renderer

# Import all renderer classes
from .default_renderer import DefaultNodeRenderer
from .error_renderer import ErrorNodeRenderer

def register_renderers(library: BaseLibrary):
    """Register all core node renderers with the renderers registry"""
    
    renderers = folder_scan_for_classes(
        library_path=__path__[0],
        library=library,
        class_filter=is_renderer
    )

    reg: RendererRegistry = library.get_registry(RendererRegistry)
    if reg:
        # Register all discovered renderers (default and error flags will be handled automatically)
        for renderer_class in renderers:
            reg._register(renderer_class, library.identity)

__all__ = [
    'DefaultNodeRenderer',
    'ErrorNodeRenderer',
    'register_renderers'
]
