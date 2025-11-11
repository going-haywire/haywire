"""
This module exports the core data components of the Haywire library, including enums,
data field specifications, and factory functions for creating data fields.

Note: DataType enum is deprecated for use in DataPortSpec and DataField.
      Use actual Python classes (int, float, str, etc.) instead.
      DataType is retained only for UI/theme color mapping purposes.
"""

from .enums import DataContainerType, FlowType
from .specs import DataPortSpec, specs_factory
from .fields import DataField, SingleField, PooledField

__all__ = [
    # Enums
    "DataContainerType",
    "FlowType",
    # Specs
    "DataPortSpec",
    "specs_factory",
    # Fields
    "DataField",
    "SingleField",
    "PooledField",
]