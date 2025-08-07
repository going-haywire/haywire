"""
This module exports the core data components of the Haywire library, including enums,
data field specifications, and factory functions for creating data fields.
"""

from .enums import DataType, DataCategory, FlowType
from .specs import DataFieldSpec, specs_factory
from .fields import DataField, SingleField, PooledField

# --- Factory functions for creating DataFieldSpec instances ---
INT = specs_factory(
        id='INT', 
        label='Integer', 
        description='Integer data type',
        type=DataType.INT,
        category=DataCategory.SCALAR,
        widget='number',
    )

FLOAT = specs_factory(
        id='FLOAT', 
        label='Float', 
        description='Float data type',
        type=DataType.FLOAT,
        category=DataCategory.SCALAR,
        widget='number',
    )
    
STRING = specs_factory(
        id='STRING', 
        label='String', 
        description='String data type',
        type=DataType.STRING,
        category=DataCategory.SCALAR,
        widget='text',
    )

__all__ = [
    # Enums
    "DataType",
    "DataCategory",
    "FlowType",
    # Specs
    "DataFieldSpec",
    "specs_factory",
    # Fields
    "DataField",
    "SingleField",
    "PooledField",
    # Factory functions
    "INT",
    "FLOAT",
    "STRING",
]