"""
Basic type conversion adapters
"""

import random
from typing import override

from haywire.core.adapter.base import BaseAdapter
from haywire.core.adapter.base import adapter

from ..types.specs import BOOL, FLOAT, INT, STRING

@adapter(
    description="Convert integer to float", 
    converts_from=INT, 
    converts_to=FLOAT
    )
class IntToFloatAdapter(BaseAdapter):   
    @override
    def convert(self, value: int) -> float:
        return float(value)

    def get_test_value(self) -> int:
        return int(random.randrange(0, 100))



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

    def get_test_value(self) -> float:
        return float(random.randrange(0, 100))
    
    
@adapter(
    description="Convert bool to integer", 
    converts_from=BOOL, 
    converts_to=INT
    )
class BoolToIntAdapter(BaseAdapter):
    """Convert bool to integer"""
   
    @override
    def convert(self, value: bool) -> int:
        return int(value)

    def get_test_value(self) -> bool:
        return random.choice([True, False])
