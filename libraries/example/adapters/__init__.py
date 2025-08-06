"""
Test adapters for the test library

This module now includes both adapters and data type definitions (merged from data/ folder).
"""

from typing import override

from haywire.core.adapter.base import BaseAdapter
from haywire.core.registry.registry import AdapterRegistry
from haywire.core.data import FLOAT

# Data type definitions (merged from data/ folder)
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

class FloatToTemperatureAdapter(BaseAdapter):
    """Convert generic float to temperature (assuming Celsius)"""
    source_type: str = FLOAT().id
    target_type: str = TEMPERATURE().id
    
    @override
    def convert(self, value: float) -> float:
        return value

class TemperatureToFloatAdapter(BaseAdapter):
    """Convert generic float to temperature (assuming Celsius)"""
    source_type: str = TEMPERATURE().id
    target_type: str = FLOAT().id
    
    @override
    def convert(self, value: float) -> float:
        return value


def register_test_adapters(adapter_registry: AdapterRegistry):
    """Register test adapters with the adapter registry using self-registering pattern"""
    # List of adapter classes to register (self-registering pattern)
    adapters = [
        FloatToTemperatureAdapter,
        TemperatureToFloatAdapter,
    ]
    
    # Register each adapter using self-registration
    for adapter_class in adapters:
        adapter_registry.register_adapter(adapter_class)
    
__all__ = [
    # Data types (merged from data/ folder)
    'TEMPERATURE',
    # Adapters
    'FloatToTemperatureAdapter',
    'TemperatureToFloatAdapter',
    'register_test_adapters'
]
