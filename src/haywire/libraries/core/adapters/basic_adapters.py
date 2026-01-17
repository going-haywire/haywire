"""
Basic type conversion adapters
"""

import random
from typing import override

from haywire.core.adapter.base import BaseAdapter
from haywire.core.adapter.base import adapter
from haywire.libraries.core.types.specs import BOOL, FLOAT, INT, STRING

@adapter(
    description="Convert integer to float", 
    converts_from=INT, 
    converts_to=FLOAT
    )
class IntToFloatAdapter(BaseAdapter):   
    @override
    def convert(self, value: int) -> float:
        return float(value)

    def test_setup(self) -> any:
        return int(random.randrange(0, 100))

    def test(self, value: int) -> any:
        return self.execute(value)


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

    def test_setup(self) -> any:
        return float(random.randrange(0, 100))
    
    def test(self, value: float) -> any:
        return self.execute(value)
    
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

    def test_setup(self) -> any:
        return random.choice([True, False])

    def test(self, value: any) -> any:
        """Test conversion with sample data"""
        return self.execute(value)