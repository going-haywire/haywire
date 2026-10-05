"""
Array Compound Type - Final Simplified Version

Key changes:
1. Uses hooks from IType (_validate_port_type, _configure_port)
2. No special port attribute setting (uses defaults from CompoundType)
3. Clean and minimal - just declares field_class
"""

from dataclasses import dataclass, field
from typing import Any, List, Optional, Type, TypeVar

from haywire.core.types import type, DataField, CompoundType
from haywire.core.types.wire import WireRole

T = TypeVar("T")

# ============================================================================
# TYPE DEFINITION
# ============================================================================


@type(
    label="Array",
    description="Homogeneous typed array",
    color="#d8e91e",
    default={"value": []},
)
class ArrayType(CompoundType[T]):
    """
    Homogeneous typed array compound type.

    Arrays store lists of elements of a specific type.
    All elements must be the same type (or compatible via adapters).

    Usage:
        # Array of floats
        ArrayType[FLOAT].as_inlet(id='numbers', default=[1.0, 2.0, 3.0])

        # Array of meshes
        ArrayType[MeshData].as_outlet(id='meshes')

    Storage: ArrayField stores List[T] with unwrapped elements
    Transfer: List of unwrapped values (primitives or instances)

    IMPORTANT:
    ArrayType declares no wire type, so it travels on its element type's; a declared one would take
    precedence (see wire_type_of).

    Hooks: Uses default implementations from IType
    - _validate_port_type: Allows all port types (inlet, outlet, config)
    - _configure_port: takes the element's colour, and refuses a control or callback element
    """

    field_class: "Optional[Type[DataField]]" = None  # Will be set to ArrayField after it's defined

    # Allows inlets, outlets, and configs

    @classmethod
    def _configure_port(cls, port, **context) -> None:
        """Take the colour of the element that declares the wire type, and refuse a control
        or callback element. An array outlet on a data wire allows several links."""
        current_type = port.type_cls.element_type_cls
        while current_type is not None:
            identity = getattr(current_type, "class_identity", None)
            wire = getattr(identity, "wire_type", None)
            if identity is not None and wire is not None:
                port.color = identity.color
                if port.is_outlet():
                    port.allow_multiple_links = wire.role is WireRole.DEPENDENT
                if wire.role is WireRole.SEQUENCE:
                    raise ValueError("ArrayType cannot have a control element type")
                if wire.role is WireRole.IMMEDIATE:
                    raise ValueError("ArrayType cannot have a callback element type")
                return
            current_type = getattr(current_type, "element_type_cls", None)

    @property
    def value(self):
        """Arrays don't have instances - this is for type checking only"""
        raise NotImplementedError("ArrayType is a type descriptor, not instantiable")


# ============================================================================
# FIELD DEFINITION
# ============================================================================


@dataclass
class ArrayField(DataField):
    """
    Field implementation for ArrayType.

    Stores list of unwrapped values with element type tracking.

    Storage: List[T] where T is unwrapped (42.0 not FLOAT(42.0))
    Worker Access: List[T] (unwrapped primitives or instances)
    Transfer: List[T] (unwrapped)
    """

    _items: List[Any] = field(default_factory=list, init=False, repr=False)

    def __post_init__(self):
        """Initialize complex field with default instance"""
        super().__post_init__()

        # Initialize from default
        initial_list = self.default_kwargs.get("value", [])
        self._items = initial_list

    def _get_own(self) -> List[Any]:
        """Return a copy of the list, e.g. ``[42.0, 3.14]`` or ``[MeshData(...)]``."""
        return list(self._items)

    def _set_own(self, value: Any) -> None:
        """Store a list, e.g. ``[1.0, 2.0, 3.0]``.

        Raises:
            TypeError: If *value* is not a list.
        """
        if not isinstance(value, list):
            raise TypeError(f"ArrayField requires list, got {value.__class__.__name__}")
        self._items = value

    def reset(self) -> None:
        """Reset to default array"""
        self._items = self.default_kwargs.get("value", [])
        self.is_dirty = True

    def has_data(self) -> bool:
        """Check if has any items"""
        return len(self._items) > 0

    # ========================================================================
    # ARRAY-SPECIFIC HELPERS
    # ========================================================================

    def get_item(self, index: int) -> Any:
        """Get specific item by index"""
        return self._items[index]

    def __len__(self) -> int:
        """Get array length"""
        return len(self._items)


# Set field_class now that ArrayField is defined
ArrayType.field_class = ArrayField
