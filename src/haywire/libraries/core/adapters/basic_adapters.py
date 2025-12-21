"""
Basic type conversion adapters
"""

from typing import override

from haywire.core.adapter.base import BaseAdapter
from haywire.core.adapter.base import adapter
from haywire.libraries.core.types.specs import FLOAT, INT, STRING

@adapter(
    description="Convert integer to float", 
    converts_from=INT, 
    converts_to=FLOAT
    )
class IntToFloatAdapter(BaseAdapter):   
    @override
    def convert(self, value: int) -> float:
        return float(value)


@adapter(
    description="Convert float to integer", 
    converts_from=FLOAT, 
    converts_to=STRING
    )
class FloatToStringAdapter(BaseAdapter):
    """Convert integer to float"""
   
    @override
    def convert(self, value: float) -> str:
        return str(value)
