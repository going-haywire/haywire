from typing import override

from haywire.core.adapter.base import BaseAdapter
from haywire.core.data import FLOAT
from .example_specs import TEMPERATURE

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