"""
Haywire Core Library

Contains fundamental nodes, widgets, adapters, and data definitions
that form the foundation of the Haywire system.
"""

from haywire.core.registry.base import BaseLibrary, LibraryMetadata
from haywire.core.registry.registry import WidgetRegistry, AdapterRegistry, RendererRegistry
from haywire.core.registry.node_system import NodeRegistry

# Import core components
from .widgets import register_widgets
from .adapters import register_adapters
from .nodes import register_nodes
from .renderers import register_renderers

# Library metadata
LIBRARY_METADATA = {
    'name': 'core',
    'version': '1.0.0',
    'description': 'Core Haywire library with fundamental components',
    'url': 'https://github.com/maybites/haywire',
    'help_url': 'https://github.com/maybites/haywire',
    'author': 'maybites',
    'author_url': 'https://maybites.ch',
    'dependencies': []
}

class Library(BaseLibrary):
    """Core Haywire library implementation"""
    
    def __init__(self, metadata: LibraryMetadata):
        super().__init__(metadata)
    
    def register_components(self, widget_registry: WidgetRegistry, renderer_registry: RendererRegistry, adapter_registry: AdapterRegistry, node_registry: NodeRegistry):
        """Register all core components with the global registries"""
        # Register widgets
        register_widgets(widget_registry)
        
        # Register adapters (now includes data types)
        register_adapters(adapter_registry)
        
        # Register renderers (node renderers)
        register_renderers(renderer_registry)
        
        # Register nodes
        register_nodes(node_registry, library_metadata=self.metadata)
    
    def validate(self) -> bool:
        """Validate that the core library is properly structured"""
        # Core library is always valid since it's part of the system
        return True
