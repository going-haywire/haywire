"""
Core renderers (node renderers) registration and exports
"""

from haywire.core.registry.auto_discover import auto_discover_classes, is_renderer
from haywire.core.registry.base import LibraryMetadata
from haywire.core.registry.registry import RendererRegistry
from haywire.core.registry.utils import camel_to_dot_case

# Import all renderer classes
from .example_renderer import ExampleNodeRenderer

def register_renderers(renderers_registry: RendererRegistry, library_metadata: LibraryMetadata):
    """Register all core node renderers with the renderers registry"""
    
    renderers = auto_discover_classes(
        library_path=__path__[0],
        class_filter=is_renderer
    )

    # Register all discovered renderers
    for renderer_class in renderers:
        print(f"Test-Registering renderer: '{renderer_class.__name__}' as :'{camel_to_dot_case(renderer_class.__name__)}'")
        #renderers_registry.register_renderer(renderer_class, library_metadata)

    # Register default and error renderers
    renderers_registry.register_renderer('example.renderer', ExampleNodeRenderer)
    
__all__ = [
    'ExampleNodeRenderer',
    'register_renderers'
]
