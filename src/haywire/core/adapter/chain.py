"""
AdapterChain - Executable adapter chain for type transformations.

This module contains the AdapterChain class which manages a sequence
of adapters that transform values from one type to another.
"""

from typing import Any, List, Optional

from .base import BaseAdapter
from ..errors import HaywireException


class AdapterChain:
    """
    Executable adapter chain for type transformations.
    
    This class:
    - Stores instantiated adapter objects (not classes)
    - Executes adapters in sequence
    - Tracks execution metrics
    - Handles errors gracefully
    
    Example:
        # Create chain: Temperature → FLOAT → INT
        chain = AdapterChain([
            TempToFloatAdapter(),
            FloatToIntAdapter()
        ])
        
        result = chain.execute(temp_value)  # Returns int
    """
    
    def __init__(self, adapters: List[BaseAdapter]):
        """
        Initialize adapter chain with instantiated adapters.
        
        Args:
            adapters: List of adapter instances in execution order
        """
        self.adapters = adapters
    
    def execute(self, value: Any) -> Any:
        """
        Execute adapter chain on value.
        
        Args:
            value: Input value (unwrapped primitive or type instance)
            
        Returns:
            Transformed value ready for target inlet            
        """        
        result = value
        for adapter in self.adapters:
            result = adapter.convert(result)
        return result
            
    def get_registry_keys(self) -> List[str]:
        """
        Get registry keys of all adapters in chain, including nested.
        
        Delegates to each adapter's get_registry_keys() method.
        Compound adapters override to include their nested adapters.
        """
        keys = []
        for adapter in self.adapters:
            keys.extend(adapter._get_registry_keys())
        return keys
    
    def get_chain_description(self) -> str:
        """Get human-readable chain description"""
        if not self.adapters:
            return "direct"
        
        names = [a.__class__.__name__ for a in self.adapters]
        return " → ".join(names)
       
