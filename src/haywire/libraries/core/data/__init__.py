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

INT_SET = specs_factory(DataType.INT, DataCategory.SET)
FLOAT_SET = specs_factory(DataType.FLOAT, DataCategory.SET)
STR_SET = specs_factory(DataType.STRING, DataCategory.SET)

FLOAT_DICT = specs_factory(DataType.FLOAT, DataCategory.DICT)
INT_DICT = specs_factory(DataType.INT, DataCategory.DICT)
STR_DICT = specs_factory(DataType.STRING, DataCategory.DICT)
OBJECT_DICT = specs_factory(DataType.OBJECT, DataCategory.DICT)

# Geometric types
VEC2 = specs_factory(DataType.OBJECT, DataCategory.SCALAR)  # 2D vector
VEC3 = specs_factory(DataType.OBJECT, DataCategory.SCALAR)  # 3D vector
VEC4 = specs_factory(DataType.OBJECT, DataCategory.SCALAR)  # 4D vector
MATRIX = specs_factory(DataType.OBJECT, DataCategory.SCALAR)  # Matrix
COLOR = specs_factory(DataType.OBJECT, DataCategory.SCALAR)  # Color
TRANSFORM = specs_factory(DataType.OBJECT, DataCategory.SCALAR)  # Transform

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
    "BOOL",
    "BYTES",
    "DICT",
    "OBJECT",
    # Array factory functions
    "INT_ARRAY",
    "FLOAT_ARRAY",
    "STR_ARRAY",
    "BOOL_ARRAY", 
    "OBJECT_ARRAY",
    # Set factory functions
    "INT_SET",
    "FLOAT_SET",
    "STR_SET",
    # Dict factory functions
    "FLOAT_DICT",
    "INT_DICT",
    "STR_DICT",
    "OBJECT_DICT",
    # Geometric factory functions
    "VEC2",
    "VEC3", 
    "VEC4",
    "MATRIX",
    "COLOR",
    "TRANSFORM"
]
