"""
Core renderers (node renderers) registration and exports
"""

from haywire.core.library.library import BaseLibrary
from haywire.core.library.registries.reg_renderer import RendererRegistry

# Import all renderer classes

def register_renderers(library: BaseLibrary):
    """Register all core node renderers with the renderers registry"""
    
    library.add_folder_to_registry(__path__[0], RendererRegistry)
    
__all__ = [
    'register_renderers'
]
