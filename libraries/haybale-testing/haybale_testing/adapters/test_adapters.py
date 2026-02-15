"""
Basic type conversion adapters
"""

import random
from typing import override

from haywire.core.adapter.base import BaseAdapter
from haywire.core.adapter.base import adapter

from ..types.test_types import TEST_BOOL, TEST_FLOAT, TEST_INT, TEST_STRING

@adapter(
    description="Convert bool to integer", 
    converts_from=TEST_BOOL, 
    converts_to=TEST_INT
    )
class BoolToIntAdapter(BaseAdapter):
    """Convert bool to integer"""
   
    @override
    def convert(self, value: bool) -> int:
        return int(value)

    def get_test_value(self) -> bool:
        return random.choice([True, False])
    
@adapter(
    description="Convert integer to float", 
    converts_from=TEST_INT, 
    converts_to=TEST_FLOAT
    )
class IntToFloatAdapter(BaseAdapter):   
    @override
    def convert(self, value: int) -> float:
        return float(value)

    def get_test_value(self) -> int:
        return int(random.randrange(0, 100))


@adapter(
    description="Convert float to string", 
    converts_from=TEST_FLOAT, 
    converts_to=TEST_STRING
    )
class FloatToStringAdapter(BaseAdapter):
    """Convert float to string"""
   
    @override
    def convert(self, value: float) -> str:
        return str(value)

    def get_test_value(self) -> float:
        return float(random.randrange(0, 100))
    