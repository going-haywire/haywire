"""
Test adapters for the test library

This module now includes both adapters and data type definitions (merged from data/ folder).
"""

from haywire.core.registry.folder_scan import folder_scan_for_classes, is_adapter
from haywire.core.registry.base import LibraryMetadata
from haywire.core.registry.registry_adapter import AdapterRegistry

def register_adapters(adapter_registry: AdapterRegistry, library_metadata: LibraryMetadata):
    """Register test adapters with the adapter registry using self-registering pattern"""

    # List of adapter classes to register (self-registering pattern)
    adapters = folder_scan_for_classes(
        library_path=__path__[0],
        class_filter=is_adapter
    )

    # Register each adapter using self-registration
    for adapter_class in adapters:
        adapter_registry.register_adapter(adapter_class)    
    
__all__ = [
    # Adapters
    'register_adapters'
]
