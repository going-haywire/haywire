"""
Basic type conversion adapters
"""

from typing import override

from haywire.core.adapter.base import BaseAdapter
from haywire.core.adapter.base import adapter

@adapter(
    description="Convert integer to float", 
    converts_from=int, 
    converts_to=float
    )
class IntToFloatAdapter(BaseAdapter):
    """Convert integer to float"""
    source_type = int
    target_type = float
   
    @override
    def convert(self, value: int) -> float:
        return float(value)
