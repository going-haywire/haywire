"""
Test Library for Haywire

Minimal test library to demonstrate multi-library support.
Contains one node, one widget, one adapter, and one data struct.
"""

from haywire.core.registry.base import BaseLibrary, LibraryMetadata
from haywire.core.registry.registry import GadgetsRegistry, WidgetRegistry, AdapterRegistry

# Import test components
from .widgets import register_test_widgets
from .adapters import register_test_adapters  # Now includes data types
from .nodes import register_test_nodes
from .gadgets import register_test_gadgets

# Library metadata
LIBRARY_METADATA = {
    'name': 'example',
    'version': '0.1.0',
    'description': 'Example library for demonstrating multi-library support',
    'author': 'Example Author',
    'dependencies': ['core']  # Depends on core library
}

class Library(BaseLibrary):
    """Example library implementation"""
    
    def __init__(self, metadata: LibraryMetadata):
        super().__init__(metadata)
    
    def register_components(self, widget_registry: WidgetRegistry, gadgets_registry: GadgetsRegistry, adapter_registry: AdapterRegistry, node_registry):
        """Register all test components with the global registries"""
        # Register widgets
        register_test_widgets(widget_registry)

        # Register gadgets
        register_test_gadgets(gadgets_registry)
        
        # Register adapters
        register_test_adapters(adapter_registry)
        
        # Register nodes
        register_test_nodes(node_registry)
    
    def validate(self) -> bool:
        """Validate that the test library is properly structured"""
        return True
