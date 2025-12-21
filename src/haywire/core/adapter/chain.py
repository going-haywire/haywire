"""
AdapterChain - Executable adapter chain for type transformations.

This module contains the AdapterChain class which manages a sequence
of adapters that transform values from one type to another.
"""

from typing import Any, List, Optional
from dataclasses import dataclass
import time

from .base import BaseAdapter
from ..errors import HaywireException


@dataclass
class AdapterChainMetrics:
    """Performance and execution metrics for adapter chains"""
    execution_count: int = 0
    total_execution_time_ms: float = 0.0
    last_execution_time_ms: float = 0.0
    average_execution_time_ms: float = 0.0
    error_count: int = 0
    last_error: Optional[str] = None


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
        self.metrics = AdapterChainMetrics()
        self._is_valid = True
        self._error: Optional[HaywireException] = None
    
    def execute(self, value: Any) -> Any:
        """
        Execute adapter chain on value.
        
        Args:
            value: Input value (unwrapped primitive or type instance)
            
        Returns:
            Transformed value ready for target inlet
            
        Raises:
            HaywireException: If transformation fails
        """
        if not self._is_valid:
            raise HaywireException(
                message="Cannot execute invalid adapter chain",
                error=self._error
            )
        
        start_time = time.perf_counter()
        
        try:
            result = value
            for adapter in self.adapters:
                result = adapter.convert(result)
            
            # Update metrics
            execution_time = (time.perf_counter() - start_time) * 1000
            self.metrics.execution_count += 1
            self.metrics.last_execution_time_ms = execution_time
            self.metrics.total_execution_time_ms += execution_time
            self.metrics.average_execution_time_ms = (
                self.metrics.total_execution_time_ms / 
                self.metrics.execution_count
            )
            
            return result
            
        except Exception as e:
            self.metrics.error_count += 1
            self.metrics.last_error = str(e)
            
            raise HaywireException(
                message=f"Adapter chain execution failed: {e}",
                error=e
            )
    
    def get_registry_keys(self) -> List[str]:
        """
        Get registry keys of all adapters in chain, including nested.
        
        Delegates to each adapter's get_registry_keys() method.
        Compound adapters override to include their nested adapters.
        """
        keys = []
        for adapter in self.adapters:
            keys.extend(adapter.get_registry_keys())
        return keys
    
    def get_chain_description(self) -> str:
        """Get human-readable chain description"""
        if not self.adapters:
            return "direct"
        
        names = [a.__class__.__name__ for a in self.adapters]
        return " → ".join(names)
    
    @property
    def is_valid(self) -> bool:
        """Check if chain is valid and executable"""
        return self._is_valid
    
    @property
    def chain_length(self) -> int:
        """Get number of adapters in chain"""
        return len(self.adapters)
    
    def invalidate(self, error: Optional[HaywireException] = None):
        """Mark chain as invalid"""
        self._is_valid = False
        self._error = error
