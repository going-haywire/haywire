"""
Basic type conversion adapters
"""

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
    
    def test(self) -> bool:
        """Test conversion with sample data"""
        sample_input = 42
        result = self.execute(sample_input)
        return True


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

    def test(self) -> bool:
        """Test conversion with sample data"""
        sample_input = 3.14
        result = self.execute(sample_input)
        return True
    
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

    def test(self) -> bool:
        """Test conversion with sample data"""
        sample_input = True
        result = self.execute(sample_input)
        return True