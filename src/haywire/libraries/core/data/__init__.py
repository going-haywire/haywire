"""
Core data definitions for the Haywire system.

This module exports the core data components including enums,
data field specifications, and factory functions for creating data fields.
Originally from haywire.core.data - moved to core library structure.
"""

import sys
import os

# Add project paths for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..'))
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from haywire.core.data.enums import DataType, DataCategory, FlowType, CouplingType
from haywire.core.data.specs import DataFieldSpec, create_data_field_factory
from haywire.core.data.fields import DataField, SingleField, PooledField

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

INT_SET = create_data_field_factory(DataType.INT, DataCategory.SET)
FLOAT_SET = create_data_field_factory(DataType.FLOAT, DataCategory.SET)
STR_SET = create_data_field_factory(DataType.STRING, DataCategory.SET)

FLOAT_DICT = create_data_field_factory(DataType.FLOAT, DataCategory.DICT)
INT_DICT = create_data_field_factory(DataType.INT, DataCategory.DICT)
STR_DICT = create_data_field_factory(DataType.STRING, DataCategory.DICT)
OBJECT_DICT = create_data_field_factory(DataType.OBJECT, DataCategory.DICT)

# Geometric types
VEC2 = create_data_field_factory(DataType.OBJECT, DataCategory.SCALAR)  # 2D vector
VEC3 = create_data_field_factory(DataType.OBJECT, DataCategory.SCALAR)  # 3D vector
VEC4 = create_data_field_factory(DataType.OBJECT, DataCategory.SCALAR)  # 4D vector
MATRIX = create_data_field_factory(DataType.OBJECT, DataCategory.SCALAR)  # Matrix
COLOR = create_data_field_factory(DataType.OBJECT, DataCategory.SCALAR)  # Color
TRANSFORM = create_data_field_factory(DataType.OBJECT, DataCategory.SCALAR)  # Transform

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
