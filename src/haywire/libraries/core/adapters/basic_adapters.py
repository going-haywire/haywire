"""
Basic type conversion adapters
"""

from typing import override

from haywire.core.adapter.base_adapter import BaseAdapter
from haywire.core.adapter.base_adapter import adapter
from ..types.specs import INT, FLOAT

@adapter(description="Convert integer to float", converts_from="INT", converts_to="FLOAT")
class IntToFloatAdapter(BaseAdapter):
    """Convert integer to float"""
    source_type: str = INT().key
    target_type: str = FLOAT().key
   
    @override
    def convert(self, value: int) -> float:
        return float(value)
