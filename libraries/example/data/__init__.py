"""
Test data definitions for the test library
"""

from haywire.core.data.enums import DataType, DataCategory
from haywire.core.data.specs import specs_factory

# Custom data type for testing
TEMPERATURE = specs_factory(
    id='TEMPERATURE', 
    label='Temperature', 
    description='Temperature data type',
    type=DataType.FLOAT,
    category=DataCategory.SCALAR,
    widget='example.temperature',
    ui={'properties': {'unit': '°C'}}
)

__all__ = [
    'TEMPERATURE'
]
