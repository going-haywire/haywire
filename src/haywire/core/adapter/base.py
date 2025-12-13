"""
Base adapter classes for type conversion
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Type, TypeVar, Union
from dataclasses import dataclass

from haywire.core.registry.identity import BaseIdentity
from haywire.core.library.utils import derive_library_identity, reg_key

@dataclass
class AdapterIdentity(BaseIdentity):
    """Core identifying attributes of an adapter"""
    converts_from: Type | None = None  # Source Python class (int, float, str, CustomType, etc.)
    converts_to: Type | None = None    # Target Python class (int, float, str, CustomType, etc.)
    priority: int = 0                  # Priority for this adapter (higher = preferred)


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
        label (str, optional): Human-readable display name for the adapter.
            Defaults to class name if not provided.
        description (str, optional): Human-readable description of the adapter.
            Defaults to empty string.
        converts_from (Type, optional): Source Python class (int, float, str, CustomType, etc.).
            Defaults to None.
        converts_to (Type, optional): Target Python class (int, float, str, CustomType, etc.).
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

        # Full customization with Python classes
        @adapter(
            registry_id="str_to_int_adapter",
            description="Converts string representations to integers with validation",
            converts_from=STRING,
            converts_to=INT,
            priority=5
        )
        class StringToIntAdapter(BaseAdapter): ...

        # Using custom types
        from mylib.types.mesh_data import MeshData
        
        @adapter(
            converts_from=DICT,
            converts_to=MeshData,
            priority=10,
            description="Convert DICT to MeshData"
        )
        class DictToMeshAdapter(BaseAdapter): ...
    """
    def decorator(inner_cls: Type[T]) -> Type[T]:
        if not issubclass(inner_cls, BaseAdapter):
            raise TypeError(
                f"@adapter can only be applied to BaseAdapter subclasses, "
                f"got {inner_cls}"
            )

        # Set defaults from class name if not provided
        kwargs.setdefault('registry_id', inner_cls.__name__)
        kwargs.setdefault('label', inner_cls.__name__)
        
        # Get library identity (survives hot-reload)
        library_identity = derive_library_identity(inner_cls)
        
        # Auto-derive registry_key
        library_id = library_identity.id if library_identity else None
        kwargs['registry_key'] = reg_key(library_id, 'adapter', kwargs['registry_id'])
        
        # Create and attach identity and library
        inner_cls.class_identity = AdapterIdentity(**kwargs)
        inner_cls.class_library = library_identity
        return inner_cls

    return decorator if cls is None else decorator(cls)

# ============================================================================
#    Base Adapter Class
# ============================================================================

class BaseAdapter(ABC):
    """Abstract base class for type adapters"""
    
    source_type: Type
    target_type: Type
    
    def __init__(self):
        if not hasattr(self, 'source_type') or not hasattr(self, 'target_type'):
            raise NotImplementedError("Adapter must define source_type and target_type")
        
    @abstractmethod
    def convert(self, value: Any) -> Any:
        """Convert the value from source type to target type"""
        pass
    
    @classmethod
    def get_conversion_info(cls) -> tuple[Type, Type]:
        """Get the source and target types for this adapter"""
        return cls.source_type, cls.target_type


class ConversionError(Exception):
    """Raised when a type conversion fails"""
    pass

