"""
Basic type conversion adapters
"""

from typing import override

from haywire.core.adapter.base import BaseAdapter
from haywire.core.inventory.registry.adapter_reg import adapter
from . import INT, FLOAT

@adapter(description="Convert integer to float", converts_from="INT", converts_to="FLOAT")
class IntToFloatAdapter(BaseAdapter):
    """Convert integer to float"""
    source_type: str = INT().id
    target_type: str = FLOAT().id
   
    @override
    def convert(self, value: int) -> float:
        return float(value)
