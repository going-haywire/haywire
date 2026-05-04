from __future__ import annotations
from abc import ABC
from typing import Any, Generic, TypeVar, final, TYPE_CHECKING
from typing_extensions import Self

from .interface import IType

if TYPE_CHECKING:
    from .fields import DataField

T = TypeVar("T")

# ============================================================================
# PRIMITIVETYPE - Wraps single primitive value
# ============================================================================


class PrimitiveType(IType, ABC, Generic[T]):
    """
    Base class for primitive type wrappers.

    Primitive types wrap Python built-in types (int, float, str, bool, bytes).
    The actual storage in PrimitiveField is unwrapped for performance.

    The wrapper serves as:
    - Type descriptor (metadata via **@type** decorator)
    - Interface contract (adapters work with types)
    - Default value creation

    Storage strategy: PrimitiveField stores unwrapped primitive (42.0 not FLOAT(42.0))

    AUTOMATIC element_type_cls:

    element_type_cls is extracted from Generic[T] parameter automatically:
        class FLOAT(PrimitiveType[float]):
            pass
        # → FLOAT.element_type_cls = float

    Examples:
    .. code-block:: python
        @type(default={'value': 12.0})
        class FLOAT(PrimitiveType[float]):
            pass

        # PrimitiveField will be used automatically
        FLOAT.field_class  # Returns PrimitiveField
        FLOAT.element_type_cls  # Returns float
    """

    # Field class set after PrimitiveField is defined
    field_class: "type[DataField[Any]] | None" = None  # Will be set to PrimitiveField

    def __init_subclass__(cls, **kwargs):
        """
        Extract element_type_cls from Generic[T] parameter.

        Called automatically when PrimitiveType is subclassed.
        """
        super().__init_subclass__(**kwargs)

        # Extract T from PrimitiveType[T]
        if hasattr(cls, "__orig_bases__"):
            for base in cls.__orig_bases__:
                if hasattr(base, "__origin__"):
                    origin_name = getattr(base.__origin__, "__name__", None)
                    if origin_name == "PrimitiveType":
                        if hasattr(base, "__args__") and base.__args__:
                            cls.element_type_cls = base.__args__[0]
                            break

    def __init__(self, value: T = None, **kwargs):
        """
        Initialize primitive with a value.

        Args:
            value: The primitive value to wrap
            **kwargs: For compatibility with create_default dict unpacking
        """
        # Handle keyword arg style from create_default
        if value is None and "value" in kwargs:
            value = kwargs["value"]

        # Fall back to class default
        if value is None:
            if hasattr(self.__class__, "class_identity"):
                default_dict = getattr(self.__class__.class_identity, "default", None)
                if isinstance(default_dict, dict):
                    value = default_dict.get("value")

        if value is None:
            raise TypeError(f"{self.__class__.__name__}() missing required argument: 'value'")

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

    # ========================================================================
    # SERIALIZATION - Stub methods for field value persistence
    # ========================================================================

    @classmethod
    def to_dict(cls, value: T) -> dict:
        """
        Serialize primitive value to dictionary.

        Default stub implementation - returns default from @type decorator.
        Override in subclasses for custom serialization logic.

        Args:
            value: The unwrapped primitive value (42.0, not FLOAT(42.0))

        Returns:
            dict: Serialized representation
        """
        # Default: return decorator default
        default_dict = getattr(cls.class_identity, "default", None)
        if isinstance(default_dict, dict):
            return default_dict
        return {}

    @classmethod
    def from_dict(cls, data: dict) -> T:
        """
        Deserialize primitive value from dictionary.

        Default stub implementation - returns default from @type decorator.
        Override in subclasses for custom deserialization logic.

        Args:
            data: Dictionary containing serialized value

        Returns:
            T: Unwrapped primitive value (42.0, not FLOAT(42.0))
        """
        # Default: return decorator default value
        value = None
        default_dict = getattr(cls.class_identity, "default", None)
        if isinstance(default_dict, dict):
            value = default_dict.get("value")
        return value


# ============================================================================
# BASETYPE - Custom complex types
# ============================================================================


class BaseType(IType, ABC):
    """
    Base class for custom complex data types.

    Complex types are user-defined dataclasses or classes that represent
    structured data (e.g., MeshData, Vector3, Transform).

    Storage strategy: BaseField stores the instance directly (instance IS the value)

    Key insight: For BaseType, value property returns self because
    the instance itself is the data container.

    AUTOMATIC element_type_cls:

    element_type_cls is set to the class itself automatically:
        class MeshData(BaseType):
            pass
        # → MeshData.element_type_cls = MeshData

    Examples:
    .. code-block:: python
        @type(default={'vertices': [], 'faces': []})
        @dataclass
        class MeshData(BaseType):
            vertices: list
            faces: list

        # BaseField will be used automatically
        MeshData.field_class  # Returns BaseField
        MeshData.element_type_cls  # Returns MeshData
    """

    # Field class set after BaseField is defined
    field_class: "type[DataField[Any]] | None" = None  # Will be set to BaseField

    def __init_subclass__(cls, **kwargs):
        """
        Set element_type_cls to self for complex types.

        Called automatically when BaseType is subclassed.

        Skips if element_type_cls is already set (e.g., by
        CompoundType.__class_getitem__).
        """
        super().__init_subclass__(**kwargs)

        # Only set if not already defined (prevents overwriting
        # parameterized types)
        if not hasattr(cls, "element_type_cls"):
            cls.element_type_cls = cls

    @property
    def value(self):
        """
        Returns self - the instance IS the value.

        Unlike PrimitiveType which wraps a primitive,
        BaseType instances are themselves the data.
        """
        return self

    # ========================================================================
    # SERIALIZATION - Stub methods for field value persistence
    # ========================================================================

    @classmethod
    def _get_default_dict(cls) -> dict:
        """
        Get default kwargs from @type decorator.

        Helper method used by default to_dict/from_dict implementations.

        Returns:
            dict: Default kwargs from decorator, or empty dict if not available
        """
        if hasattr(cls, "class_identity"):
            default_dict = getattr(cls.class_identity, "default", None)
            if isinstance(default_dict, dict):
                return default_dict
        return {}

    def to_dict(self) -> dict:
        """
        Serialize BaseType instance to dictionary.

        Default implementation:
        - If dataclass: uses dataclasses.asdict()
        - Otherwise: returns decorator default

        Override in subclasses for custom serialization logic.

        Returns:
            dict: Serialized representation

        Example override:
            def to_dict(self) -> dict:
                return {
                    'vertices': self.vertices.tolist(),
                    'faces': self.faces.tolist()
                }
        """
        import dataclasses

        if dataclasses.is_dataclass(self):
            return dataclasses.asdict(self)

        # Fallback: return decorator default
        return self._get_default_dict()

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        """
        Deserialize BaseType instance from dictionary.

        Default implementation:
        - If dataclass: unpacks data as constructor kwargs
        - Otherwise: uses decorator default as kwargs

        Override in subclasses for custom deserialization logic.

        Args:
            data: Dictionary containing serialized data

        Returns:
            Self: New instance of this type

        Example override:
            @classmethod
            def from_dict(cls, data: dict) -> Self:
                return cls(
                    vertices=np.array(data['vertices']),
                    faces=np.array(data['faces'])
                )
        """
        import dataclasses

        if dataclasses.is_dataclass(cls):
            return cls(**data)

        # Fallback: use decorator default
        return cls(**cls._get_default_dict())


# ============================================================================
# COMPOUNDTYPE - Collections with element types
# ============================================================================


class CompoundType(BaseType, ABC, Generic[T]):
    """
    Abstract base for compound/collection types.

    Compound types hold multiple elements of a specific type.
    They track element_type_cls for type safety and adapter support.

    Storage strategy: CompoundField subclasses store unwrapped elements

    HIERARCHICAL element_type_cls:

    element_type_cls is set during parameterization to the IType:
        ArrayType[FLOAT].element_type_cls → FLOAT
        ArrayType[FLOAT].element_type_cls.element_type_cls → float

    This creates a two-level hierarchy for drilling down to Python types.

    Type parameterization via __class_getitem__:
        ArrayType[FLOAT].as_inlet(id='numbers')
        PooledType[MeshData].as_inlet(id='meshes')

    Subclasses must:
    - Define field_class (ArrayField, PooledField, etc.)
    - Can override _validate_port_type() to restrict inlet/outlet
    - Can override _configure_port() to add port attributes

    Examples:

    .. code-block:: python
        @type(default={'value': []})
        class ArrayType(CompoundType[T]):
            field_class = ArrayField

        # Usage with type parameterization:
        ArrayType[FLOAT].as_inlet(id='numbers')
        # → element_type_cls = FLOAT

        # Or explicit element_type_cls:
        ArrayType.as_inlet(id='numbers', element_type_cls=FLOAT)
    """

    # Subclasses MUST override field_class
    field_class: "type[DataField[Any]] | None" = None

    # Cache for parameterized classes
    # this cache is cleared in the decorator when a class is recreated by hot-reload
    _parameterized_cache: "dict[Any, type]" = {}

    @classmethod
    def __class_getitem__(cls, element_type_cls: type[IType]):
        """
        Create parameterized compound type with caching.

        Returns a cached class instance to ensure type identity:
        ArrayType[FLOAT] is ArrayType[FLOAT] → True

        Each parameterized class has its own element_type_cls.
        """
        if not hasattr(cls, "_parameterized_cache"):
            cls._parameterized_cache = {}

        # Check cache
        cache_key = (cls, element_type_cls)
        if cache_key in cls._parameterized_cache:
            return cls._parameterized_cache[cache_key]

        # Create new parameterized class
        class_name = f"{cls.__name__}[{element_type_cls.__name__}]"

        # Build attributes dict - only include if they exist on parent
        attrs = {
            "element_type_cls": element_type_cls,
            "field_class": cls.field_class,
            # Share the cache
            "_parameterized_cache": cls._parameterized_cache,
        }

        # Copy identity attributes if they exist (after decoration)
        if hasattr(cls, "class_identity"):
            attrs["class_identity"] = cls.class_identity
        if hasattr(cls, "class_library"):
            attrs["class_library"] = cls.class_library

        # Use the parent class's metaclass explicitly
        # This prevents ABC/metaclass issues
        metaclass = type(cls)

        parameterized_cls = metaclass(class_name, (cls,), attrs)

        # Cache and return
        cls._parameterized_cache[cache_key] = parameterized_cls
        return parameterized_cls
