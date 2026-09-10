from __future__ import annotations
from abc import ABC
from typing import Any, Generic, TypeVar, TYPE_CHECKING
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
            # __orig_bases__ is a typing-runtime tuple the checker types as object.
            for base in cls.__orig_bases__:  # ty: ignore[not-iterable]
                if hasattr(base, "__origin__"):
                    origin_name = getattr(base.__origin__, "__name__", None)
                    if origin_name == "PrimitiveType":
                        if hasattr(base, "__args__") and base.__args__:
                            cls.element_type_cls = base.__args__[0]
                            break

    def __init__(self, value: "T | None" = None, **kwargs):
        """
        Initialize primitive with a value.

        A primitive instance structurally CANNOT hold absence: ``None`` is read
        as "not supplied" at every step, and a ``None`` that survives all the
        fallbacks raises. So ``@type(default={'value': None})`` on a
        PrimitiveType is a latent ``TypeError`` — anything that instantiates the
        type (``create_default``, ``PrimitiveField.to_dict``) explodes, even
        though ``create_field`` itself never does. A type whose domain includes
        absence belongs in the ``WrapperType`` family, whose ``__init__``
        accepts ``None`` deliberately.

        Args:
            value: The primitive value to wrap. May be None during construction;
                falls back to kwargs["value"] (from create_default dict unpacking)
                or to class_identity.default["value"]. Raises if no value resolved.
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
    def value(self) -> T:
        """Returns the wrapped primitive value.

        Note: this property is intentionally not subclass-overridable in spirit
        — subclasses should provide their own typed wrapper around _value.
        """
        return self._value

    @value.setter
    def value(self, val: T):
        """Sets the wrapped primitive value."""
        self._value = val

    # ========================================================================
    # SERIALIZATION - Stub methods for field value persistence
    # ========================================================================

    def to_dict(self) -> dict:
        """
        Serialize this primitive to a dictionary.

        Default implementation wraps the unwrapped value as {'value': self._value}.
        Override in subclasses for custom serialization logic.

        Returns:
            dict: Serialized representation
        """
        return {"value": self._value}

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

        Raises:
            ValueError: If no default value is configured on class_identity.
        """
        # Default: return decorator default value
        default_dict = getattr(cls.class_identity, "default", None)
        if isinstance(default_dict, dict) and "value" in default_dict:
            return default_dict["value"]
        raise ValueError(
            f"{cls.__name__}.from_dict has no value to return: no class_identity.default "
            f"is configured. Override from_dict in subclasses, or set a default in @type(default=...)."
        )


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
            # Guarded by is_dataclass; ty's narrowing leaves an intersection it
            # won't accept as a DataclassInstance.
            return dataclasses.asdict(self)  # ty: ignore[invalid-argument-type]

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

        Each parameterized class has its own element_type_cls but SHARES the
        parent's ``class_identity`` object — so every ``ArrayType[*]`` reports
        one registry key, one colour, one widget_key, and differs only in its
        element. Round-tripping works anyway because ``serialize_element_type``
        writes the shared key plus a recursive ``element_type`` recipe. The
        consequence to know: anything reading appearance off the identity
        (pin colour, widget properties) cannot tell ``ArrayType[FLOAT]`` from
        ``ArrayType[STRING]``. ``WrapperType`` deliberately does NOT share —
        it stamps a per-parameterization identity so the element's appearance
        survives (``_wrapped_identity``).
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
        attrs: dict[str, Any] = {
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

        parameterized_cls = metaclass(class_name, (cls,), attrs)  # type: ignore[misc]

        # Cache and return
        cls._parameterized_cache[cache_key] = parameterized_cls
        return parameterized_cls


# ============================================================================
# WRAPPERTYPE - Exactly one value of another type, or absence
# ============================================================================


#: Absence-tolerant field classes, keyed by the element's own field class.
#: Shared so ``OPTIONAL[INT]`` built twice yields one field class, matching
#: ``_parameterized_cache``'s identity guarantee for the types themselves.
_ABSENCE_TOLERANT_FIELDS: "dict[type, type]" = {}


def _absence_tolerant_field(base_field_cls: type) -> type:
    """Return a subclass of *base_field_cls* whose ``set_value`` accepts ``None``.

    A wrapped element keeps its own storage behaviour while a value is PRESENT —
    ``OPTIONAL[INT]`` still coerces through ``INTField``, so an optional int and a
    plain int answer identically for the same write. Absence has to bypass that
    coercion (``int(None)`` raises), so the ``None`` branch stores through
    ``PrimitiveField.set_value`` directly: it skips the element field's override
    while keeping the change event that widgets and promoted ports listen on.

    Restricted to ``PrimitiveField`` descendants, which is what "the cell holds a
    bare value or ``None``" means in storage terms. A ``BaseField`` element has no
    unwrapped slot to put absence in and would need its own design.
    """
    from .fields import PrimitiveField

    if not (isinstance(base_field_cls, type) and issubclass(base_field_cls, PrimitiveField)):
        raise TypeError(
            f"a wrapper type cannot wrap an element stored by {base_field_cls.__name__}: "
            f"absence is only defined for PrimitiveField storage (a bare value or None). "
            f"Wrap a primitive-shaped IType instead."
        )

    cached = _ABSENCE_TOLERANT_FIELDS.get(base_field_cls)
    if cached is not None:
        return cached

    class _AbsenceTolerantField(base_field_cls):  # type: ignore[valid-type,misc]
        """``base_field_cls``, plus the ability to hold absence."""

        def set_value(self, value: Any, source_id: "str | None" = None) -> None:
            if value is None:
                PrimitiveField.set_value(self, None, source_id)
                return
            super().set_value(value, source_id)

        def get_stored_type(self) -> "type[IType]":
            """The ELEMENT type — what flows on an edge.

            ``type_cls`` remains the wrapper (``OPTIONAL[INT]``), which is what
            ``OptionalWidget`` and the identity read. Everything that asks what
            travels along a link — ``EdgeWrapper``'s adapter resolution,
            ``pin_render``'s icon and colour, reroute creation from an outlet —
            gets ``INT``, so a promoted optional behaves as an ordinary INT pin
            and needs no ``OPTIONAL[T] -> T`` adapter.
            """
            element = self.type_cls.element_type_cls
            assert element is not None  # __class_getitem__ always sets it
            return element

        def accepts_absence(self) -> bool:
            """True — this is the field class that exists to hold ``None``."""
            return True

    _AbsenceTolerantField.__name__ = f"AbsenceTolerant{base_field_cls.__name__}"
    _AbsenceTolerantField.__qualname__ = _AbsenceTolerantField.__name__
    _ABSENCE_TOLERANT_FIELDS[base_field_cls] = _AbsenceTolerantField
    return _AbsenceTolerantField


def _wrapped_identity(wrapper_identity: Any, element_type_cls: type[IType]) -> Any:
    """The wrapper's identity, wearing the element's appearance.

    ``registry_key`` and ``widget_key`` stay the WRAPPER's: a saved graph must
    resolve back to the wrapper (``serialize_element_type`` writes the wrapper's
    key plus an ``element_type`` recipe), and the wrapper's own widget is what
    renders the row. ``color`` and the declared widget properties come from the
    ELEMENT, so ``OPTIONAL[VEC3F]`` reaches ``VecWidget`` with the ``vec_meta`` it
    cannot render without, and an optional int keeps INT's hue instead of one
    shared "wrapper" grey.
    """
    import dataclasses

    element_identity = getattr(element_type_cls, "class_identity", None)
    if element_identity is None:
        return wrapper_identity
    element_props = (getattr(element_identity, "widget_config", None) or {}).get("properties", {})
    wrapper_props = (getattr(wrapper_identity, "widget_config", None) or {}).get("properties", {})
    return dataclasses.replace(
        wrapper_identity,
        color=element_identity.color,
        widget_config={"properties": {**element_props, **wrapper_props}},
    )


class WrapperType(IType, ABC, Generic[T]):
    """
    A value of another IType, or absence.

    The fourth type family, beside ``PrimitiveType`` (one primitive),
    ``BaseType`` (one structured instance) and ``CompoundType`` (N elements).
    A wrapper qualifies one element type with a state that type cannot express
    on its own — ``OPTIONAL[INT]`` is an int that may also be *nothing*.

    Use it when a value's domain needs a member the element type has no room
    for, and where borrowing one of the element's own values as a sentinel
    would corrupt its range. The framework's only member today is ``OPTIONAL``,
    which exists because wrapping a library means mirroring its ``Optional[T]``
    parameters, and "don't pass this at all" is a real state.

    BEHAVIOUR:

    Reads and writes are the element's, unchanged, while a value is present.
    ``OPTIONAL[INT]`` keeps ``INTField``'s int coercion, so an optional int and
    a plain int answer identically for the same write; only ``None`` takes a
    different path. Storage is the element's own field class made
    absence-tolerant (``_absence_tolerant_field``), so the cell holds a bare
    value or ``None`` and a worker reads exactly that.

    Appearance is the element's too. A parameterized wrapper carries its OWN
    ``class_identity`` — the wrapper's ``registry_key`` and ``widget_key`` (a
    saved graph must resolve back to the wrapper, and the wrapper's widget
    renders the row) over the element's colour and declared widget properties
    (``_wrapped_identity``). So ``OPTIONAL[VEC3F]`` reaches ``VecWidget`` with
    the ``vec_meta`` it needs, and an optional int keeps INT's hue.

    A wrapper is a SCALAR for every other purpose — one value, not a
    collection — so adapter resolution and pin rendering treat it as one.

    AUTHORING ONE:

    .. code-block:: python
        @type(default={'value': None}, widget_key=widget_keys.OPTIONAL_WIDGET)
        class OPTIONAL(WrapperType[T]):
            '''docstring'''

    That is the whole declaration. Do not set ``field_class`` or
    ``element_type_cls``: ``__class_getitem__`` derives both from the element at
    parameterization time, along with the merged identity.

    USING ONE:

    .. code-block:: python
        OPTIONAL[INT]                      # cached: is-identical on re-subscript
        OPTIONAL[INT].element_type_cls     # INT
        setting[OPTIONAL[INT]](None, min=1, max=1000, label="Top K")

    LIMITS (all raise at parameterization time, not later):

    - the element must be stored by a ``PrimitiveField`` — "absence" means a
      bare value or ``None`` in an unwrapped slot, and a ``BaseField`` element
      has nowhere to put it;
    - a wrapper may not wrap a wrapper;
    - the element must declare a ``field_class``.

    Note for anyone extending the type system: a wrapper is deliberately not a
    ``CompoundType``, because that predicate means "container of N" and is
    dispatched on elsewhere. See ADR 0033.
    """

    field_class: "type[DataField[Any]] | None" = None

    #: Cache of parameterized classes; cleared by the @type decorator on reload.
    _parameterized_cache: "dict[Any, type]" = {}

    def __init__(self, value: Any = None, **kwargs: Any) -> None:
        """Wrap *value*, which may legitimately be ``None``.

        Unlike ``PrimitiveType.__init__``, absence is not an error here — it is
        the whole point of the family, and ``create_default()`` relies on it
        (the decorator default is ``{'value': None}``).
        """
        if value is None and "value" in kwargs:
            value = kwargs["value"]
        self._value: Any = value

    @property
    def value(self) -> Any:
        """The wrapped value, or ``None`` for absence."""
        return self._value

    def to_dict(self) -> dict:
        """Serialize, delegating a PRESENT value to the element's own encoding."""
        if self._value is None:
            return {"value": None}
        element = self.element_type_cls
        if isinstance(element, type) and issubclass(element, IType):
            return element(value=self._value).to_dict()  # type: ignore[call-arg]
        return {"value": self._value}

    @classmethod
    def from_dict(cls, data: dict) -> Any:
        """Deserialize to the bare value, or ``None``.

        Absence is stored as an explicit ``null``, so a missing/``None`` value
        reads back as absence rather than as the element's default.
        """
        if data.get("value") is None:
            return None
        element = cls.element_type_cls
        if isinstance(element, type) and issubclass(element, IType):
            return element.from_dict(data)
        return data.get("value")

    @classmethod
    def __class_getitem__(cls, element_type_cls: type[IType]):
        """
        Create the parameterized wrapper, caching so type identity holds:
        ``OPTIONAL[INT] is OPTIONAL[INT]`` → True.

        Beyond ``CompoundType``'s version this also derives an absence-tolerant
        ``field_class`` from the element, merges the element's appearance into a
        per-parameterization identity, and refuses to wrap another wrapper.
        """
        if not isinstance(element_type_cls, type):
            # A TypeVar, not an element: this is the generic DECLARATION
            # (``class OPTIONAL(WrapperType[T])``), not a parameterization.
            # Hand it back to Generic — deriving a field class from a TypeVar
            # would fail, and there is nothing to cache.
            return super().__class_getitem__(element_type_cls)  # type: ignore[misc]

        if not hasattr(cls, "_parameterized_cache"):
            cls._parameterized_cache = {}

        cache_key = (cls, element_type_cls)
        if cache_key in cls._parameterized_cache:
            return cls._parameterized_cache[cache_key]

        if issubclass(element_type_cls, WrapperType):
            # Absence has no degrees: a second wrapper can only mean the first.
            # Caught here rather than surfacing later as a widget-delegation
            # failure far from the declaration that caused it.
            raise TypeError(
                f"{cls.__name__}[{element_type_cls.__name__}] is not a valid type — "
                f"a wrapper type cannot wrap another wrapper type. Wrap the inner "
                f"element type directly."
            )

        element_field_cls = getattr(element_type_cls, "field_class", None)
        if element_field_cls is None:
            raise TypeError(
                f"{cls.__name__}[{getattr(element_type_cls, '__name__', element_type_cls)!r}]: "
                f"the element type declares no field_class, so it has no storage to "
                f"make absence-tolerant."
            )

        class_name = f"{cls.__name__}[{element_type_cls.__name__}]"
        attrs: dict[str, Any] = {
            "element_type_cls": element_type_cls,
            "field_class": _absence_tolerant_field(element_field_cls),
            # Share the cache
            "_parameterized_cache": cls._parameterized_cache,
        }
        if hasattr(cls, "class_identity"):
            attrs["class_identity"] = _wrapped_identity(cls.class_identity, element_type_cls)
        if hasattr(cls, "class_library"):
            attrs["class_library"] = cls.class_library

        # Use the parent class's metaclass explicitly (prevents ABC/metaclass issues)
        metaclass = type(cls)
        parameterized_cls = metaclass(class_name, (cls,), attrs)  # type: ignore[misc]

        cls._parameterized_cache[cache_key] = parameterized_cls
        return parameterized_cls
