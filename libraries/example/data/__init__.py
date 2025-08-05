"""
Test data definitions for the test library
"""

from haywire.core.data.enums import DataType, DataCategory
from haywire.core.data.specs import specs_factory

# Custom data type for testing
TEMPERATURE = specs_factory(DataType.FLOAT, DataCategory.SCALAR)

__all__ = [
    'TEMPERATURE'
]
