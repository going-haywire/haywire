"""
Base adapter classes for type conversion
"""

from abc import ABC, abstractmethod
from typing import Any

from haywire.core.data.enums import DataType

class BaseAdapter(ABC):
    """Abstract base class for type adapters"""
    
    source_type: DataType
    target_type: DataType
    
    def __init__(self):
        if not hasattr(self, 'source_type') or not hasattr(self, 'target_type'):
            raise NotImplementedError("Adapter must define source_type and target_type")
    
    @abstractmethod
    def can_convert(self, value: Any) -> bool:
        """Check if the value can be converted"""
        pass
    
    @abstractmethod
    def convert(self, value: Any) -> Any:
        """Convert the value from source type to target type"""
        pass
    
    @classmethod
    def get_conversion_info(cls) -> tuple[DataType, DataType]:
        """Get the source and target types for this adapter"""
        return cls.source_type, cls.target_type


class ConversionError(Exception):
    """Raised when a type conversion fails"""
    pass
