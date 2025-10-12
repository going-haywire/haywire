"""
Test adapters for the test library

This module now includes both adapters and data type definitions (merged from data/ folder).
"""

from haywire.core.adapter.base_adapter import is_adapter
from haywire.core.inventory.folder_scan_for_classes import folder_scan_for_classes
from haywire.core.inventory.registry.adapter_reg import AdapterRegistry

def register_adapters(library):
    """Register adapters with the adapter registry using self-registering pattern"""

    # List of adapter classes to register (self-registering pattern)
    adapters = folder_scan_for_classes(
        library_path=__path__[0],
        library=library,
        class_filter=is_adapter
    )

    reg = library.get_registry(AdapterRegistry)
    if reg:
        # Register each adapter using self-registration
        for adapter_class in adapters:
            reg.register_adapter(adapter_class)    
    
__all__ = [
    # Adapters
    'register_adapters'
]
