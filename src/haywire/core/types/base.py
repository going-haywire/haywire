from __future__ import annotations
from abc import ABC
from typing import TYPE_CHECKING, TypeVar
from typing_extensions import Self

from ..adapter.base import BaseAdapter
from ..adapter.registry import AdapterRegistry
from .interface import IType
from .type_to_dataport import TypeToDataPort


class BaseType(IType, TypeToDataPort, ABC):
    """
    Base class for all Haywire data types.
    
    Basic implementation for all types.

    The @type decorator will set the 'default' metadata, which create_default() uses.
        
    Attributes (set by @type_ decorator):
        class_identity: DataPortIdentity with all type metadata
        class_library: LibraryIdentity of the library this type belongs to
    """
    
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

    def is_value_type(self, compare: type) -> bool:
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
            @type(default={})  # Indicate to use create_default
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


