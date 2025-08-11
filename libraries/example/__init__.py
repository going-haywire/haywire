"""
Test Library for Haywire

Minimal test library to demonstrate multi-library support.
Contains one node, one widget, one adapter, and one data struct.
"""

from haywire.core.inventory.registry.renderer import RendererRegistry
from haywire.core.inventory.registry.adapter import AdapterRegistry
from haywire.core.inventory.registry.widget import WidgetRegistry
from haywire.core.inventory.base import BaseLibrary, LibraryMetadata
from haywire.core.inventory.registry.node import NodeRegistry

# Import test components
from .widgets import register_widgets
from .adapters import register_adapters  # Now includes data types
from .nodes import register_nodes
from .renderers import register_renderers

# Library metadata
LIBRARY_METADATA = {
    'name': 'example',
    'version': '0.1.0',
    'description': 'Example library for demonstrating multi-library support',
    'url': 'https://github.com/author/haywire_library',
    'help_url': 'https://docs.github.io/haywire_library',
    'author': 'Example Author',
    'author_url': 'https://author_url',
    'dependencies': ['haywire.core'],  # Depends on core library
    'file_watcher': False  # Enable file watching for this library
}

class Library(BaseLibrary):
    """Example library implementation"""
       
    def register_components(self, widget_registry: WidgetRegistry, renderers_registry: RendererRegistry, adapter_registry: AdapterRegistry, node_registry: NodeRegistry):
        """Register all test components with the global registries"""
        # Register widgets
        register_widgets(widget_registry, library_metadata=self.metadata)

        # Register renderers
        register_renderers(renderers_registry, library_metadata=self.metadata)
        
        # Register adapters
        register_adapters(adapter_registry, library_metadata=self.metadata)
        
        # Register nodes
        register_nodes(node_registry, library_metadata=self.metadata)
    
    def validate(self) -> bool:
        """Validate that the test library is properly structured"""
        return True
