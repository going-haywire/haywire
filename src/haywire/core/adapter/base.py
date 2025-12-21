"""
Base adapter classes for type conversion
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Callable, List, Type, TypeVar, Union
from dataclasses import dataclass

from haywire.core.registry.identity import BaseIdentity
from haywire.core.library.utils import derive_library_identity, reg_key

if TYPE_CHECKING:
    from haywire.core.types.interface import IType
    from .chain import AdapterChain

@dataclass
class AdapterIdentity(BaseIdentity):
    """
    Core identifying attributes of an adapter.
    
    IType-based: converts_from and converts_to are IType classes.
    """
    converts_from: type['IType'] | None = None  # Source IType (FLOAT, Temperature, etc.)
    converts_to: type['IType'] | None = None    # Target IType (INT, MeshData, etc.)
    priority: int = 0                            # Priority (higher = preferred)


# ============================================================================
#    Decorator
# ============================================================================

T = TypeVar('T')

def adapter(
    cls: Type[T] = None, /, **kwargs
) -> Union[Type[T], Callable[[Type[T]], Type[T]]]:
    """
    Decorator to register a class as a type adapter.
    
    Accepts any AdapterIdentity field as a keyword argument.
    
    Args:
        registry_id (str, optional): Unique identifier for the adapter.
            Defaults to class name if not provided.
        label (str, optional): Human-readable display name.
            Defaults to class name if not provided.
        description (str, optional): Human-readable description.
            Defaults to empty string.
        converts_from (type[IType], optional): Source IType class.
            Defaults to None.
        converts_to (type[IType], optional): Target IType class.
            Defaults to None.
        priority (int, optional): Priority (higher = preferred).
            Defaults to 0.
    
    Any other keyword arguments will be passed through to AdapterIdentity.
    See the AdapterIdentity dataclass for complete list of fields.

    Usage:
        # Minimal usage
        @adapter
        class MyAdapter(BaseAdapter): ...

        # Common customization
        @adapter(description="Temperature to float conversion")
        class MyAdapter(BaseAdapter): ...

        # Full customization with IType classes
        @adapter(
            registry_id="temp_to_float",
            description="Convert Temperature (Celsius) to FLOAT",
            converts_from=Temperature,
            converts_to=FLOAT,
            priority=5
        )
        class TempToFloatAdapter(BaseAdapter): ...

        # Multi-hop chain example
        @adapter(
            converts_from=Temperature,
            converts_to=Kelvin,
            priority=10,
            description="Celsius to Kelvin"
        )
        class TempToKelvinAdapter(BaseAdapter): ...
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
        
        Examples:
            # Primitive to primitive
            def convert(self, celsius: float) -> float:
                return (celsius * 9/5) + 32
            
            # Complex to complex
            def convert(self, mesh: MeshData) -> PointCloud:
                return PointCloud(points=mesh.vertices)
            
            # Primitive to string
            def convert(self, value: float) -> str:
                return f\"{value:.2f}\"
        """
        pass
    
    def get_registry_keys(self) -> List[str]:
        """
        Get all registry keys for this adapter and any nested adapters.
        
        Base implementation returns only this adapter's key.
        Compound adapters (ArrayArrayAdapter, StructuralAdapter) should
        override to include nested adapter keys.
        
        Returns:
            List of registry keys for hot-reload dependency tracking
        """
        return [self.class_identity.registry_key]


class PassThroughAdapter(BaseAdapter):
    """
    Identity adapter that passes values through unchanged.
    
    Used when source and target types are the same.
    Registered automatically by AdapterRegistry.
    """
       
    def convert(self, value: Any) -> Any:
        """Pass through unchanged"""
        return value

    def get_registry_keys(self) -> List[str]:
        return []


class ChainAdapter(BaseAdapter):
    """
    Utility adapter that wraps an AdapterChain.
    
    Used internally by AdapterFactory when a multi-adapter chain
    needs to be injected as a single element adapter in compound
    type transformations.
    
    Example:
        # ARRAY[FLOAT] → ARRAY[STRING] where FLOAT → STRING
        # requires multiple adapters: FLOAT → INT → STRING
        element_chain = AdapterChain([
            FloatToIntAdapter(),
            IntToStringAdapter()
        ])
        
        # Wrap chain to inject into ArrayArrayAdapter
        wrapper = ChainAdapter(element_chain)
        container = ArrayArrayAdapter(element_adapter=wrapper)
    """
    
    def __init__(self, chain: 'AdapterChain'):
        """
        Args:
            chain: The adapter chain to wrap
        """
        self._chain = chain
        
        # Create synthetic identity based on wrapped chain
        chain_desc = chain.get_chain_description()
        self.class_identity = type('AdapterIdentity', (), {
            'registry_key': f"chain_{id(chain)}",
            'label': f"Chain: {chain_desc}",
        })()
    
    def convert(self, value: Any) -> Any:
        """Execute wrapped chain"""
        return self._chain.execute(value)
    
    def get_registry_keys(self) -> List[str]:
        """Delegate to wrapped chain"""
        return self._chain.get_registry_keys()


class ConversionError(Exception):
    """Raised when a type conversion fails"""
    pass

