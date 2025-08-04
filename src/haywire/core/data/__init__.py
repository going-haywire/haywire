"""
This module exports the core data components of the Haywire library, including enums,
data field specifications, and factory functions for creating data fields.
"""

from .enums import DataType, DataCategory, FlowType, CouplingType
from .specs import DataFieldSpec, create_data_field_factory
from .fields import DataField, SingleField, PooledField

# --- Factory functions for creating DataFieldSpec instances ---
INT = create_data_field_factory(DataType.INT)
FLOAT = create_data_field_factory(DataType.FLOAT)
STR = create_data_field_factory(DataType.STRING)
BOOL = create_data_field_factory(DataType.BOOL)
BYTES = create_data_field_factory(DataType.BYTES)
DICT = create_data_field_factory(DataType.DICT)
OBJECT = create_data_field_factory(DataType.OBJECT)

INT_ARRAY = create_data_field_factory(DataType.INT, DataCategory.LIST)
FLOAT_ARRAY = create_data_field_factory(DataType.FLOAT, DataCategory.LIST)
STR_ARRAY = create_data_field_factory(DataType.STRING, DataCategory.LIST)
BOOL_ARRAY = create_data_field_factory(DataType.BOOL, DataCategory.LIST)
OBJECT_ARRAY = create_data_field_factory(DataType.OBJECT, DataCategory.LIST)

__all__ = [
    # Enums
    "DataType",
    "DataCategory",
    "FlowType",
    "CouplingType",
    # Specs
    "DataFieldSpec",
    "create_data_field_factory",
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