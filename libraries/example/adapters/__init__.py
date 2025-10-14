"""
Test adapters for the test library

This module now includes both adapters and data type definitions (merged from data/ folder).
"""

from haywire.core.inventory.library import BaseLibrary
from haywire.core.inventory.registry.adapter_reg import AdapterRegistry

def register_adapters(library: BaseLibrary):
    """Register adapters with the adapter registry using self-registering pattern"""

    library.add_folder_to_registry(__path__[0], AdapterRegistry)
    
__all__ = [
    # Adapters
    'register_adapters'
]
