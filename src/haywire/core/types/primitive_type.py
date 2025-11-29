from abc import ABC
from typing import Generic, TypeVar, final

from haywire.core.types.base import BaseType

T = TypeVar('T')

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
    @final
    def value(self) -> T:
        """Returns the wrapped primitive value."""
        return self._value

    @value.setter
    @final
    def value(self, val: T):
        """Sets the wrapped primitive value."""
        self._value = val