"""
Base adapter classes for type conversion
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Callable, Type, TypeVar, Union
from dataclasses import dataclass

from haywire.core.registry.identity import BaseIdentity
from haywire.core.library.utils import derive_library_identity, reg_key

if TYPE_CHECKING:
    from haywire.core.types.interface import IType

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
    """
    Base class for type adapters.
    
    Key design:
    - Type-level operations use IType classes (for registration, matching)
    - Value-level operations use unwrapped primitives/instances (for conversion)
    
    This creates clean separation between type system and runtime values.
    
    Example:
        # Register with type classes
        registry.register_adapter(
            source=Temperature,  # IType class
            target=FLOAT,        # IType class
            adapter=TemperatureToFloatAdapter
        )
        
        # Convert with unwrapped values
        adapter = TemperatureToFloatAdapter()
        result = adapter.convert(25.0)  # float -> float (not FLOAT -> FLOAT)
    """
    
    @classmethod
    @abstractmethod
    def can_adapt(cls, source: type['IType'], target: type['IType']) -> bool:
        """
        Type-level check: Can we adapt between these TYPE CLASSES?
        
        This is used for registration and validation.
        Operates on type classes, not instances or values.
        
        Args:
            source: Source IType class (e.g., Temperature)
            target: Target IType class (e.g., FLOAT)
        
        Returns:
            True if this adapter can convert source to target
        
        Example:
            class TemperatureToFloatAdapter(BaseAdapter):
                @classmethod
                def can_adapt(cls, source, target):
                    return source == Temperature and target == FLOAT
        """
        pass

    @abstractmethod
    def convert(self, value: Any) -> Any:
        """
        Value-level conversion: Convert UNWRAPPED value.
        
        This is where actual data transformation happens.
        Operates on unwrapped primitives or instances, not IType wrappers.
        
        Args:
            value: Unwrapped value from source field
                   - For primitives: 25.0 (not FLOAT(25.0))
                   - For complex: MeshData(...) instance
        
        Returns:
            Unwrapped value for target field
            - For primitives: 77.0 (not FLOAT(77.0))
            - For complex: PointCloud(...) instance
        
        Note: Type is already validated via can_adapt().
              This method focuses purely on value conversion.
        
        Examples:
            # Primitive to primitive
            def convert(self, celsius: float) -> float:
                return (celsius * 9/5) + 32
            
            # Complex to complex
            def convert(self, mesh: MeshData) -> PointCloud:
                return PointCloud(points=mesh.vertices)
            
            # Primitive to string
            def convert(self, value: float) -> str:
                return f"{value:.2f}"
        """
        pass

    @classmethod
    def get_conversion_info(cls) -> tuple[Type, Type]:
        """Get the source and target types for this adapter"""
        return cls.source_type, cls.target_type


class IdentityAdapter(BaseAdapter):
    """
    Identity adapter that passes values through unchanged.
    
    Useful when source and target types are the same or
    when a derived type needs to convert to its base.
    """
    
    def __init__(self, source: type['IType'], target: type['IType']):
        self.source = source
        self.target = target
    
    @classmethod
    def can_adapt(cls, source: type['IType'], target: type['IType']) -> bool:
        """Identity can adapt if types are the same"""
        return source == target
    
    def convert(self, value: Any) -> Any:
        """Pass through unchanged"""
        return value


class ConversionError(Exception):
    """Raised when a type conversion fails"""
    pass

