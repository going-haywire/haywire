"""
This module exports the core data components of the Haywire library, including enums,
data port identity, and data fields.

Note: DataType enum is deprecated. Use actual Python classes (int, float, str, etc.) instead.
      DataType is retained only for UI/theme color mapping purposes.
"""

from .enums import ContainerType, FlowType
from ..types.identity import DataPortIdentity
from .fields import DataField, SingleField, PooledField

# Backward compatibility
from .specs import DataPortSpec, specs_factory

__all__ = [
    # Enums
    "ContainerType",
    "FlowType",
    # Identity (new unified system)
    "DataPortIdentity",
    # Fields
    "DataField",
    "SingleField",
    "PooledField",
    # Backward compatibility
    "DataPortSpec",
    "specs_factory",
]
