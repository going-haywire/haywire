"""
Core data definitions for the Haywire system.

This module exports the core data components including enums,
data field specifications, and factory functions for creating data fields.
Originally from haywire.core.data - moved to core library structure.
"""

from haywire.core.data.enums import DataType, DataCategory, FlowType, CouplingType
from haywire.core.data.specs import DataFieldSpec, specs_factory
from haywire.core.data.fields import DataField, SingleField, PooledField

# --- Factory functions for creating DataFieldSpec instances ---
INT = specs_factory(
        id='INT', 
        label='Integer', 
        description='Integer data type',
        data_type=DataType.INT,
        category=DataCategory.SCALAR,
        widget='number',
    )

FLOAT = specs_factory(
        id='FLOAT', 
        label='Float', 
        description='Float data type',
        data_type=DataType.FLOAT,
        category=DataCategory.SCALAR,
        widget='number',
    )
    
STR = specs_factory(
        id='STR', 
        label='String', 
        description='String data type',
        data_type=DataType.STRING,
        category=DataCategory.SCALAR,
        widget='text',
    )

__all__ = [
    # Enums
    "DataType",
    "DataCategory", 
    "FlowType",
    "CouplingType",
    # Specs
    "DataFieldSpec",
    "specs_factory",
    # Fields
    "DataField",
    "SingleField",
    "PooledField",
    # Basic factory functions
    "INT",
    "FLOAT",
    "STR", 
]
