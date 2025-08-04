"""
Test adapters for the test library
"""

import sys
import os
from typing import Any

# Add project paths for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from haywire.libraries.core.adapters.base import BaseAdapter, ConversionError
from haywire.libraries.registry import AdapterRegistry
from haywire.core.data.enums import DataType


class FloatToTemperatureAdapter(BaseAdapter):
    """Convert generic float to temperature (assuming Celsius)"""
    source_type = DataType.FLOAT
    target_type = DataType.FLOAT  # Temperature is still a float, but semantically different
    
    def can_convert(self, value: Any) -> bool:
        return isinstance(value, (float, int))
    
    def convert(self, value: Any) -> float:
        if not self.can_convert(value):
            raise ConversionError(f"Cannot convert {type(value)} to temperature")
        # For this example, we just pass through the value
        # In a real scenario, this might involve unit conversion or validation
        return float(value)


def register_test_adapters(adapter_registry: AdapterRegistry):
    """Register test adapters with the adapter registry"""
    adapter_registry.register_adapter(
        FloatToTemperatureAdapter.source_type,
        FloatToTemperatureAdapter.target_type,
        FloatToTemperatureAdapter
    )


__all__ = [
    'FloatToTemperatureAdapter',
    'register_test_adapters'
]
