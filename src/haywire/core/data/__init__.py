"""
This module exports the core data components of the Haywire library, including enums,
data field specifications, and factory functions for creating data fields.
"""

from .enums import DataType, DataCategory, FlowType, CouplingType
from .specs import DataFieldSpec, specs_factory
from .fields import DataField, SingleField, PooledField

# --- Factory functions for creating DataFieldSpec instances ---
INT = specs_factory(DataType.INT)
FLOAT = specs_factory(DataType.FLOAT)
STR = specs_factory(DataType.STRING)
BOOL = specs_factory(DataType.BOOL)
BYTES = specs_factory(DataType.BYTES)
DICT = specs_factory(DataType.DICT)
OBJECT = specs_factory(DataType.OBJECT)

INT_ARRAY = specs_factory(DataType.INT, DataCategory.LIST)
FLOAT_ARRAY = specs_factory(DataType.FLOAT, DataCategory.LIST)
STR_ARRAY = specs_factory(DataType.STRING, DataCategory.LIST)
BOOL_ARRAY = specs_factory(DataType.BOOL, DataCategory.LIST)
OBJECT_ARRAY = specs_factory(DataType.OBJECT, DataCategory.LIST)

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
    # Factory functions
    "INT",
    "FLOAT",
    "STR",
    "BOOL",
    "BYTES",
    "DICT",
    "OBJECT",
    "INT_ARRAY",
    "FLOAT_ARRAY",
    "STR_ARRAY",
    "BOOL_ARRAY",
    "OBJECT_ARRAY",
]