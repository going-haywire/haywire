"""
Basic type conversion adapters
"""

from typing import override

from haywire.core.adapter.base import BaseAdapter
from haywire.core.data import INT, FLOAT

class IntToFloatAdapter(BaseAdapter):
    """Convert integer to float"""
    source_type: str = INT().id
    target_type: str = FLOAT().id
   
    @override
    def convert(self, value: int) -> float:
        return float(value)
