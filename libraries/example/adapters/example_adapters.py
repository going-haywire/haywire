from typing import override

from haywire.core.adapter.base_adapter import BaseAdapter
from haywire.core.adapter.base_adapter import adapter
from haywire.libraries.core.adapters import FLOAT
from .example_specs import TEMPERATURE

@adapter(description="Convert generic float to temperature (assuming Celsius)", converts_from="FLOAT", converts_to="TEMPERATURE")
class FloatToTemperatureAdapter(BaseAdapter):
    """Convert generic float to temperature (assuming Celsius)"""
    source_type: str = FLOAT().id
    target_type: str = TEMPERATURE().id

    @override
    def convert(self, value: float) -> float:
        return value

@adapter(description="Convert temperature to generic float", converts_from="TEMPERATURE", converts_to="FLOAT")
class TemperatureToFloatAdapter(BaseAdapter):
    """Convert generic float to temperature (assuming Celsius)"""
    source_type: str = TEMPERATURE().id
    target_type: str = FLOAT().id

    @override
    def convert(self, value: float) -> float:
        return value