"""
Core adapter registration and exports

This module now includes both adapters and core data type definitions (merged from data/ folder).
"""

from haywire.core.inventory.library import BaseLibrary
from haywire.core.inventory.registry.adapter_reg import AdapterRegistry
from haywire.core.data.enums import DataType, DataContainerType
from haywire.core.data.specs import specs_factory


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

def register_adapters(library: BaseLibrary):
    """Register all core adapters with the adapter registry"""

    library.add_folder_to_registry(__path__[0], AdapterRegistry)

__all__ = [
    # Data types (merged from data/ folder)
    'register_adapters'
]
