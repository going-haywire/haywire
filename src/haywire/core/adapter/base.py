"""
Base adapter classes for type conversion
"""

from abc import ABC, abstractmethod
import inspect
from typing import Any, override

from haywire.core.data.enums import DataType


# For adapters
def is_adapter(cls):
    """Check if a class is a valid Haywire adapter class."""
    try:
        return (inspect.isclass(cls) and
                issubclass(cls, BaseAdapter) and
                cls != BaseAdapter)
    except TypeError:
        return False

class BaseAdapter(ABC):
    """Abstract base class for type adapters"""
    
    source_type: str
    target_type: str
    
    def __init__(self):
        if not hasattr(self, 'source_type') or not hasattr(self, 'target_type'):
            raise NotImplementedError("Adapter must define source_type and target_type")
        
    @abstractmethod
    def convert(self, value: Any) -> Any:
        """Convert the value from source type to target type"""
        pass
    
    @classmethod
    def get_conversion_info(cls) -> tuple[str, str]:
        """Get the source and target types for this adapter"""
        return cls.source_type, cls.target_type


class ConversionError(Exception):
    """Raised when a type conversion fails"""
    pass
