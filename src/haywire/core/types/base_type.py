"""
Type Base - Base class for all Haywire data types.

This module provides the TypeBase class which serves as the foundation for all
data types in the Haywire system, both primitive type variants and custom compound types.
"""

from __future__ import annotations
from abc import ABC
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, TypeVar, Generic
from typing import get_type_hints
from typing_extensions import Self

from haywire.core.adapter.base_adapter import BaseAdapter

from ..library.registries.reg_adapter import AdapterRegistry
from ..data.enums import FlowType
from ..library.library_identity import LibraryIdentity
from .identity import DataPortIdentity
from .type_interface import IType

if TYPE_CHECKING:
    from .ports import PortInlet, PortOutlet

T = TypeVar('T')

class TypeToDataPort:
    """
    Mixin providing methods to create data ports from this type.
    
    These are convenience classmethods that delegate to shared utilities.
    """

    @classmethod
    def as_inlet(cls, id: str, **kwargs) -> PortInlet:
        """
        Create an inlet from this type.
        
        Args:
            id: Port identifier within the node (e.g., 'input_value')
            **kwargs: Override identity attributes or add port-specific fields
        
        Returns:
            PortInlet configured with this type's identity
        
        Example:
            FLOAT.as_inlet('value', default=1.0)
            Temperature.as_inlet('temp', default=25.0, ui={'unit': '°C'})
        """
        from haywire.core.types.utils import create_port_base
        from haywire.core.types.ports import PortInlet
        return create_port_base(cls, PortInlet, id, **kwargs)
    
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
        from haywire.core.types.utils import create_port_base
        from haywire.core.types.ports import PortOutlet
        return create_port_base(cls, PortOutlet, id, **kwargs)
    
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
    
    Supports both positional and keyword argument styles:
    - FLOAT(5.0)           # Direct usage
    - FLOAT(value=5.0)     # Explicit keyword
    - FLOAT(**{'value': 5.0})  # From create_default()
    """

    def __init__(self, value: T = None, **kwargs):
        """
        Initialize primitive with a value.
        
        Args:
            value: The primitive value to wrap
            **kwargs: For compatibility with create_default dict unpacking
        """
        # Handle keyword arg style from create_default
        if value is None and 'value' in kwargs:
            value = kwargs['value']
        
        # Fall back to class default
        if value is None:
            if hasattr(self.__class__, 'class_identity'):
                default_dict = getattr(self.__class__.class_identity, 'default', None)
                if isinstance(default_dict, dict):
                    value = default_dict.get('value')
                    
        if value is None:  
            raise TypeError(
                f"{self.__class__.__name__}() missing required argument: 'value'"
            )
        
        self._value: T = value

    @property
    def value(self) -> T:
        """Returns the wrapped primitive value."""
        return self._value
    
    @value.setter
    def value(self, val: T):
        """Sets the wrapped primitive value."""
        self._value = val