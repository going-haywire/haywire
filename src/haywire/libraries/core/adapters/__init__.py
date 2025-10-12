"""
Core adapter registration and exports

This module now includes both adapters and core data type definitions (merged from data/ folder).
"""

from haywire.core.adapter.base_adapter import is_adapter
from haywire.core.inventory.registry.adapter_reg import AdapterRegistry
from haywire.core.inventory.folder_scan import folder_scan_for_classes
from haywire.core.data.enums import DataType, DataContainerType
from haywire.core.data.specs import DataFieldSpec, specs_factory


# --- Factory functions for creating DataFieldSpec instances ---
INT = specs_factory(
        id='INT', 
        label='Integer', 
        description='Integer data type',
        type=DataType.INT,
        container=DataContainerType.SINGLE,
        widget='haywire.core:number.widget',
    )

FLOAT = specs_factory(
        id='FLOAT', 
        label='Float', 
        description='Float data type',
        type=DataType.FLOAT,
        container=DataContainerType.SINGLE,
        widget='haywire.core:number.widget',
    )
    
STRING = specs_factory(
        id='STRING', 
        label='String', 
        description='String data type',
        type=DataType.STRING,
        container=DataContainerType.SINGLE,
        widget='haywire.core:text.input.widget',
    )

def register_adapters(library):
    """Register all core adapters with the adapter registry"""
    
    # Discover all adapter classes in this library
    adapters = folder_scan_for_classes(
        library_path=__path__[0],
        metadata=library.metadata,
        class_filter=is_adapter
    )

    reg = library.get_registry(AdapterRegistry)
    if reg:
        # Register all discovered adapters
        for adapter_class in adapters:
            reg.register_adapter(adapter_class, library.metadata)

__all__ = [
    # Data types (merged from data/ folder)
    'register_adapters'
]
