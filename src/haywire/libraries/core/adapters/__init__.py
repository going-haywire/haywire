"""
Core adapter registration and exports

This module now includes both adapters and core data type definitions (merged from data/ folder).
"""
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
