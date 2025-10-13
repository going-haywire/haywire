"""
Base adapter classes for type conversion
"""

from abc import ABC, abstractmethod
import inspect
from typing import Any, Callable, Type, override, TypeVar, Optional, Union
from dataclasses import dataclass

from haywire.core.data.enums import DataType

@dataclass
class AdapterIdentity:
    """Core identifying attributes of an adapter"""
    registry_id: str = ''  # Set by user for unique ID within library - fallback to class name
    registry_key: str = ''  # Full unique key including library ID - set by registry
    description: str = ''
    converts_from: str | None = None  # Source data type identifier
    converts_to: str | None = None    # Target data type identifier
    priority: int = 0                 # Priority for this adapter (higher = preferred)

# For adapters
def is_adapter(cls):
    """Check if a class is a valid Haywire adapter class."""
    try:
        return (inspect.isclass(cls) and
                issubclass(cls, BaseAdapter) and
                cls != BaseAdapter and
                hasattr(cls, 'class_identity'))
    except TypeError:
        return False

# ============================================================================
#    Decorator
# ============================================================================

T = TypeVar('T')

def adapter(cls: Type[T] = None, /, **kwargs) -> Union[Type[T], Callable[[Type[T]], Type[T]]]:
    """
    Decorator to register a class as a type adapter.
    
    Accepts any AdapterIdentity field as a keyword argument. Common arguments include:
    
    Args:
        registry_id (str, optional): Unique identifier for the adapter within its library.
            Defaults to class name if not provided.
        description (str, optional): Human-readable description of the adapter.
            Defaults to empty string.
        converts_from (str, optional): Source data type identifier.
            Defaults to None.
        converts_to (str, optional): Target data type identifier.
            Defaults to None.
        priority (int, optional): Priority for this adapter (higher = preferred).
            Defaults to 0.
    
    Any other keyword arguments will be passed through to the AdapterIdentity constructor.
    See the AdapterIdentity dataclass for the complete list of available fields.

    Usage:
        # Minimal usage - uses class name for registry_id
        @adapter
        class MyAdapter(BaseAdapter): ...

        # Common customization
        @adapter(description="String to integer conversion adapter")
        class MyAdapter(BaseAdapter): ...

        # Full customization
        @adapter(
            registry_id="str_to_int_adapter",
            description="Converts string representations to integers with validation",
            converts_from="STRING",
            converts_to="INT",
            priority=5
        )
        class StringToIntAdapter(BaseAdapter): ...

        # High priority adapter
        @adapter(
            converts_from="FLOAT", 
            converts_to="INT", 
            priority=10,
            description="High priority float to int converter"
        )
        class HighPriorityAdapter(BaseAdapter): ...
    """
    def decorator(inner_cls: Type[T]) -> Type[T]:
        if not issubclass(inner_cls, BaseAdapter):
            raise TypeError(f"@adapter can only be applied to BaseAdapter subclasses, got {inner_cls}")

        # Set defaults from class name if not provided
        kwargs.setdefault('registry_id', inner_cls.__name__)
        
        inner_cls.class_identity = AdapterIdentity(**kwargs)
        return inner_cls

    return decorator if cls is None else decorator(cls)

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

