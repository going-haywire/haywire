"""
Test adapters for the test library
"""

from typing import override

from haywire.core.adapter.base import BaseAdapter
from haywire.core.registry.registry import AdapterRegistry
from haywire.core.data import FLOAT
from ..data import TEMPERATURE

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
    """Register test adapters with the adapter registry"""
    adapter_registry.register_adapter(
        FloatToTemperatureAdapter.source_type,
        FloatToTemperatureAdapter.target_type,
        FloatToTemperatureAdapter
    )
    adapter_registry.register_adapter(
        TemperatureToFloatAdapter.source_type,
        TemperatureToFloatAdapter.target_type,
        TemperatureToFloatAdapter
    )
    
__all__ = [
    'FloatToTemperatureAdapter',
    'TemperatureToFloatAdapter',
    'register_test_adapters'
]
