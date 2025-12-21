"""
Compound type adapters for array transformations.

These adapters handle array-to-array transformations and are registered
like any other adapter. The AdapterFactory injects element adapters.
"""

from typing import Any, List, override

from haywire.core.adapter.base import adapter, BaseAdapter
from haywire.libraries.core.types.array_type import ArrayType


@adapter(
    registry_id='array_array',
    label='Array to Array',
    description='Transform array elements (ArrayType[X] → ArrayType[Y])',
    converts_from=ArrayType,
    converts_to=ArrayType,
    priority=0
)
class ArrayArrayAdapter(BaseAdapter):
    """
    Transforms ArrayType[X] → ArrayType[Y].
    
    Accepts optional element_adapter for element transformation.
    Always skips None values to prevent chain failures.
    
    If you need to preserve None values, use a dedicated filter node.
    
    Examples:
        # ArrayType[FLOAT] → ArrayType[FLOAT] (no element transformation)
        adapter = ArrayArrayAdapter()
        result = adapter.convert([1.0, 2.0, 3.0])
        # → [1.0, 2.0, 3.0]
        
        # ArrayType[FLOAT] → ArrayType[STRING] (with element transformation)
        float_to_str = FloatToStringAdapter()
        adapter = ArrayArrayAdapter(element_adapter=float_to_str)
        result = adapter.convert([1.5, None, 2.7])
        # → ["1.50", "2.70"]  (None skipped)
    """
    
    def __init__(self, element_adapter: BaseAdapter = None):
        """
        Initialize array adapter.
        
        Args:
            element_adapter: Optional adapter for element transformation.
                           Injected by AdapterFactory when element types differ.
        """
        self._element_adapter = element_adapter
    
    @override
    def convert(self, values: List[Any]) -> List[Any]:
        """
        Transform each element or pass through.
        
        Args:
            values: List of source elements
            
        Returns:
            List of transformed elements (None values skipped)
        """
        return [
            self._element_adapter.convert(v)
            for v in values
            if v is not None  # Always skip None
        ]
    
    @override
    def get_registry_keys(self) -> List[str]:
        """
        Get registry keys including nested element adapter.
        
        Returns:
            List with this adapter's key plus element adapter's keys
        """
        keys = [self.class_identity.registry_key]
        
        if self._element_adapter:
            keys.extend(self._element_adapter.get_registry_keys())
        
        return keys
