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

    reg = library.get_registry(RendererRegistry)
    if reg:
        # Register all discovered renderers
        for renderer_class in renderers:
            reg.register_renderer(renderer_class, library.identity)

        # Set fallback renderers using class references
        reg.register_default_renderer(DefaultNodeRenderer)
        reg.register_error_renderer(ErrorNodeRenderer)

__all__ = [
    'DefaultNodeRenderer',
    'ErrorNodeRenderer',
    'register_renderers'
]
