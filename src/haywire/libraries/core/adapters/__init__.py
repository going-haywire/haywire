"""
Core adapter registration and exports

This module now includes both adapters and core data type definitions (merged from data/ folder).
"""

from haywire.core.adapter.base import is_adapter
from haywire.core.inventory.registry.adapter import AdapterRegistry
from haywire.core.inventory.folder_scan import folder_scan_for_classes
from haywire.core.inventory.registry.library import LibraryMetadata
from haywire.core.data.enums import DataType, DataCategory
from haywire.core.data.specs import DataFieldSpec, specs_factory


# --- Factory functions for creating DataFieldSpec instances ---
INT = specs_factory(
        id='INT', 
        label='Integer', 
        description='Integer data type',
        type=DataType.INT,
        category=DataCategory.SCALAR,
        widget='haywire.core:number.widget',
    )

FLOAT = specs_factory(
        id='FLOAT', 
        label='Float', 
        description='Float data type',
        type=DataType.FLOAT,
        category=DataCategory.SCALAR,
        widget='haywire.core:number.widget',
    )
    
STRING = specs_factory(
        id='STRING', 
        label='String', 
        description='String data type',
        type=DataType.STRING,
        category=DataCategory.SCALAR,
        widget='haywire.core:text.input.widget',
    )

def register_adapters(adapter_registry: AdapterRegistry, library_metadata: LibraryMetadata):
    """Register all core adapters with the adapter registry"""
    
    # Discover all adapter classes in this library
    adapters = folder_scan_for_classes(
        library_path=__path__[0],
        class_filter=is_adapter
    )

    # Register all discovered adapters
    for adapter_class in adapters:
        adapter_registry.register_adapter(adapter_class, library_metadata)

__all__ = [
    # Data types (merged from data/ folder)
    'register_adapters'
]
