"""
Base adapter classes for type conversion
"""

from abc import ABC, abstractmethod
import inspect
from typing import Any, Callable, Type, override, TypeVar, Optional, Union

from haywire.core.data.enums import DataType

# ============================================================================
#    Decorator
# ============================================================================

T = TypeVar('T')

def adapter(cls: Type[T] = None, /, *,
            description: str,
            converts_from: str = None,
            converts_to: str = None,
            registry_id: Optional[str] = None,
            priority: int = 0) -> Union[Type[T], Callable[[Type[T]], Type[T]]]:
    """
    Decorator to register a class as a type adapter.

    Args:
        registry_id: Unique identifier for the adapter
        description: Human-readable description
        converts_from: Source data type identifier
        converts_to: Target data type identifier
        priority: Priority for this adapter (higher = preferred)

    Usage:
        @adapter
        class MyAdapter(BaseAdapter): ...

        @adapter(registry_id="custom_adapter", converts_from="int", converts_to="str")
        class MyAdapter(BaseAdapter): ...

        @adapter(priority=10, converts_from="FLOAT", converts_to="INT")
        class HighPriorityAdapter(BaseAdapter): ...
    """
    def decorator(inner_cls: Type[T]) -> Type[T]:
        if not issubclass(inner_cls, BaseAdapter):
            raise TypeError(f"@adapter can only be applied to BaseAdapter subclasses, got {inner_cls}")

        # Store adapter metadata
        inner_cls.class_identity = {
            'description': description or '',
            'converts_from': converts_from,
            'converts_to': converts_to,
            'priority': priority,
            'registry_id': registry_id or inner_cls.__name__
        }

        return inner_cls

    if cls is None:
        return decorator
    return decorator(cls)


# For adapters
def is_adapter(cls):
    """Check if a class is a valid Haywire adapter class."""
    try:
        return (inspect.isclass(cls) and
                issubclass(cls, BaseAdapter) and
                cls != BaseAdapter)
    except TypeError:
        return False

# ============================================================================
#    Decorator
# ============================================================================

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

