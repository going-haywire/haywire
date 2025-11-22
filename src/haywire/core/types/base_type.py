"""
Type Base - Base class for all Haywire data types.

This module provides the TypeBase class which serves as the foundation for all
data types in the Haywire system, both primitive type variants and custom compound types.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, TypeVar, Generic
from typing import get_type_hints
from typing_extensions import Self

from haywire.core.adapter.base_adapter import BaseAdapter
from haywire.core.types.utils import normalize_and_validate_default

from ..library.registries.reg_adapter import AdapterRegistry
from ..data.enums import FlowType
from ..library.library_identity import LibraryIdentity
from .identity import DataPortIdentity
from .ports import PortInlet, PortOutlet

T = TypeVar('T')

class IType(ABC):
    """
    Interface for all Haywire data types.
    """
    @abstractmethod
    def has_adapter(self, type_cls: type[BaseType], adapter_registry: AdapterRegistry) -> bool:
        """
        Check if this type has an adapter to the specified type.
        
        Args:
            type_cls: Target TypeBase subclass to check for adapter 
        Returns:
            True if an adapter exists, False otherwise
        """
        pass

    @abstractmethod
    def is_type(self, compare: type) -> bool:
        """
        Check if the value is an instance of the given type.
        
        Args:
            compare: Type to check against
            
        Returns:
            True if value is an instance of compare
        """
        pass

    @abstractmethod
    def get_adapter(self, type_cls: type[BaseType], adapter_registry: AdapterRegistry) -> BaseAdapter:
        """
        Get an adapter instance to convert this type to the specified type.
        
        Args:
            type_cls: Target TypeBase subclass to adapt to  
        Returns:
            Adapter instance for the conversion
        """
        pass

    @classmethod
    @abstractmethod
    def create_default(cls) -> Self:
        """Create a default instance of this type."""
        pass


class TypeToDataPort():
    """
    Mixin providing methods to create data ports from this type.
    """

    @classmethod
    def as_inlet(cls, id: str, **kwargs) -> PortInlet:
        """
        Create an inlet from this type.
        
        Args:
            id: Port identifier within the node (e.g., 'input_value')
            **kwargs: Override identity attributes or add port-specific fields
                     (default, flow_type, callback, is_pooled, etc.)
        
        Returns:
            PortInlet configured with this type's identity
        
        Example:
            FLOAT.as_inlet('value', default=1.0)
            Temperature.as_inlet('temp', default=25.0, ui={'unit': '°C'})
        """
        
        # Prepare kwargs with id and defaults
        kwargs['id'] = id

        # Normalize and validate default if provided
        if 'default' in kwargs:
            kwargs['default'] = normalize_and_validate_default(
                kwargs['default'],
                cls,
                context=f"as_inlet('{id}')"
            )
                    
        # Merge identity with overrides
        port_kwargs = {
            **asdict(cls.class_identity),
            **kwargs
        }
        
        # Create the inlet
        inlet = PortInlet(**port_kwargs)
        
        # Set the library reference
        inlet.class_library = cls.class_library
        
        # Store creation recipe for serialization (if from registered type)
        if cls.class_identity.registry_key and not cls.class_identity.registry_key.startswith('default:'):
            inlet._creation_recipe = {
                'registry_key': cls.class_identity.registry_key,
                'method': 'as_inlet',
                'kwargs': kwargs
            }
        
        return inlet
    
    @classmethod
    def as_outlet(cls, id: str, **kwargs) -> PortOutlet:
        """
        Create an outlet from this type.
        
        Args:
            id: Port identifier within the node (e.g., 'output_result')
            **kwargs: Override identity attributes or add port-specific fields
        
        Returns:
            PortOutlet configured with this type's identity
        
        Example:
            FLOAT.as_outlet('result')
            MeshData.as_outlet('mesh')
        """
        
        # Prepare kwargs with id and defaults
        kwargs['id'] = id
        
        # Normalize and validate default if provided
        if 'default' in kwargs:
            kwargs['default'] = normalize_and_validate_default(
                kwargs['default'],
                cls,
                context=f"as_outlet('{id}')"
            )
                    
        # Merge identity with overrides
        port_kwargs = {
            **asdict(cls.class_identity),
            **kwargs
        }
        
        # Create the outlet
        outlet = PortOutlet(**port_kwargs)
        
        # Set the library reference (use getattr for safety during hot-reload)
        outlet.class_library = getattr(cls, 'class_library', None)
        
        # Remove default from kwargs for storage (it was already used in creation)
        kwargs.pop('default', None)
        
        # Store creation recipe for serialization (if from registered type)
        if cls.class_identity.registry_key and not cls.class_identity.registry_key.startswith('default:'):
            outlet._creation_recipe = {
                'registry_key': cls.class_identity.registry_key,
                'method': 'as_outlet',
                'kwargs': kwargs
            }
        
        return outlet
    
    @classmethod
    def as_config(cls, id: str, **kwargs) -> PortInlet:
        """
        Create a config inlet (no visible pin) from this type.
        
        Args:
            id: Config identifier within the node
            **kwargs: Override identity attributes
        
        Returns:
            PortInlet with flow_type=NONE (no visible pin)
        
        
        Example:
            FLOAT.as_config('threshold', default=0.5)
        """
        return cls.as_inlet(id, flow_type=FlowType.NONE, **kwargs)


class BaseType(IType, TypeToDataPort, ABC):
    """
    Base class for all Haywire data types.
    
    Basic implementation for all types.

    The @type decorator will set the 'default' metadata, which create_default() uses.
        
    Attributes (set by @type_ decorator):
        class_identity: DataPortIdentity with all type metadata
        class_library: LibraryIdentity of the library this type belongs to
    """
    
    # Set by @type decorator:
    class_identity: DataPortIdentity
    # Set by type registration:
    class_library: LibraryIdentity

    @property
    def value(self):
        """
        Returns the value of this type.
        For complex types: returns self
        For primitive types: returns the wrapped primitive
        """
        return self
        
    def has_adapter(self, type_cls: type[BaseType], adapter_registry: AdapterRegistry) -> bool:
        return adapter_registry.has_adapter(type(self), type_cls)

    def get_adapter(self, type_cls: type[BaseType], adapter_registry: AdapterRegistry) -> BaseAdapter:
        return adapter_registry.get_adapter(type(self), type_cls)


    def is_type(self, compare: type) -> bool:
        return isinstance(self.value, compare)
    
    @classmethod
    def create_default(cls) -> Self:
        """
        Create a default instance.
        
        Default implementation uses the 'default' dict from @type decorator
        as constructor kwargs. Override this method for complex default logic
        (e.g., numpy arrays, mutable collections, computed values).
        
        Returns:
            New instance with default values
            
        Examples:
            # Simple case - uses decorator's default dict:
            @type(default={'vertices': [], 'faces': []})
            class MeshData(BaseType):
                pass
            
            # Complex case - overrides for custom logic:
            @type(default={'value': None})  # Just for serialization hint
            class NumpyArray(PrimitiveType[np.ndarray]):
                @classmethod
                def create_default(cls):
                    return cls(np.zeros((2, 3), dtype=np.int32))
        """
        default_kwargs = cls.class_identity.default
        if default_kwargs is None:
            default_kwargs = {}
        
        try:
            return cls(**default_kwargs)
        except Exception as e:
            raise TypeError(
                f"Cannot create default instance of {cls.__name__} using default={default_kwargs}. "
                f"Consider overriding create_default() classmethod for complex initialization. "
                f"Original error: {e}"
            ) from e


class PrimitiveType(BaseType, ABC, Generic[T]):
    """
    Base class for primitive type wrappers.
    
    Primitive types wrap Python built-in types (int, float, str, bool, bytes)
    and their variants (e.g., Temperature extends FLOAT which wraps float).
    
    For simple primitives, the decorator's default={'value': X} is used directly.
    For complex primitives (numpy arrays, etc.), override create_default().
    
    Examples:
        # Simple primitive:
        @type(default={'value': 12.0})
        @dataclass
        class FLOAT(PrimitiveType[float]):
            pass
        
        # Derived type inherits default:
        @type(registry_id='temperature')
        class Temperature(FLOAT):   
            pass  # Uses inherited default={'value': 12.0}
        
        # Complex primitive with override:
        @type(default={'value': None})
        class NumpyArray(PrimitiveType[np.ndarray]):
            @classmethod
            def create_default(cls):
                return cls(np.zeros((2, 3)))
    """

    def __init__(self, value: T):
        self._value: T = value
    
    @property
    def value(self) -> T:
        """Returns the wrapped primitive value."""
        return self._value
    
    @value.setter
    def value(self, val: T):
        """Sets the wrapped primitive value."""
        self._value = val
