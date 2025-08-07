"""
Test Library for Haywire

Minimal test library to demonstrate multi-library support.
Contains one node, one widget, one adapter, and one data struct.
"""

from haywire.core.registry.base import BaseLibrary, LibraryMetadata
from haywire.core.registry.registry import GadgetsRegistry, WidgetRegistry, AdapterRegistry
from haywire.core.registry.node_system import NodeRegistry

# Import test components
from .widgets import register_widgets
from .adapters import register_adapters  # Now includes data types
from .nodes import register_nodes
from .gadgets import register_gadgets

# Library metadata
LIBRARY_METADATA = {
    'name': 'example',
    'version': '0.1.0',
    'description': 'Example library for demonstrating multi-library support',
    'url': 'https://github.com/author/haywire_library',
    'help_url': 'https://docs.github.io/haywire_library',
    'author': 'Example Author',
    'author_url': 'https://author_url',
    'dependencies': ['core']  # Depends on core library
}

class Library(BaseLibrary):
    """Example library implementation"""
    
    def __init__(self, metadata: LibraryMetadata):
        super().__init__(metadata)
    
    def register_components(self, widget_registry: WidgetRegistry, gadgets_registry: GadgetsRegistry, adapter_registry: AdapterRegistry, node_registry: NodeRegistry):
        """Register all test components with the global registries"""
        # Register widgets
        register_widgets(widget_registry)

        # Register gadgets
        register_gadgets(gadgets_registry)
        
        # Register adapters
        register_adapters(adapter_registry)
        
        # Register nodes
        register_nodes(node_registry, library_metadata=self.metadata)
    
    def validate(self) -> bool:
        """Validate that the test library is properly structured"""
        return True
