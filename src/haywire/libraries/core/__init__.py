"""
Haywire Core Library

Contains fundamental nodes, widgets, adapters, and data definitions
that form the foundation of the Haywire system.
"""

from haywire.core.registry.base import BaseLibrary, LibraryMetadata
from haywire.core.registry.registry import WidgetRegistry, AdapterRegistry

# Import core components
from .widgets import register_core_widgets
from .adapters import register_core_adapters
from .nodes import register_core_nodes
from .data import *  # Import all data definitions


# Library metadata
LIBRARY_METADATA = {
    'name': 'core',
    'version': '1.0.0',
    'description': 'Core Haywire library with fundamental components',
    'author': 'Haywire System',
    'dependencies': []
}


class Library(BaseLibrary):
    """Core Haywire library implementation"""
    
    def __init__(self, metadata: LibraryMetadata):
        super().__init__(metadata)
    
    def register_components(self, widget_registry: WidgetRegistry, adapter_registry: AdapterRegistry, node_registry):
        """Register all core components with the global registries"""
        # Register widgets
        register_core_widgets(widget_registry)
        
        # Register adapters
        register_core_adapters(adapter_registry)
        
        # Register nodes
        register_core_nodes(node_registry)
    
    def validate(self) -> bool:
        """Validate that the core library is properly structured"""
        # Core library is always valid since it's part of the system
        return True
