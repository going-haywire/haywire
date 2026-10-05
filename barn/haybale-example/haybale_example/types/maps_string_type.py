from dataclasses import dataclass, field
from typing import Any, cast, Dict, Optional, Type, TypeVar

from haywire.core.types import type, DataField, CompoundType, IType
from haywire.core.types.fields import element_from_dict, element_to_dict
from haywire.ui import elements as hui
from haywire.barn.builtin.wires import DataWire

T = TypeVar("T")

# ============================================================================
# TYPE DEFINITION
# ============================================================================


@type(
    wire_type=DataWire,
    label="Array",
    description="Map with key type string",
    color="#39f55f",
    icon=hui.icon.list,
    default={"value": []},
)
class MapsStringType(CompoundType[T]):
    """
    Maps string keyed typed array compound type.

    Arrays store lists of elements of a specific type.
    All elements must be the same type (or compatible via adapters).

    Usage:
        # MapsStringType of floats
        MapsStringType[FLOAT].as_inlet(id='numbers', default=[1.0, 2.0, 3.0])

        # MapsStringType of meshes
        MapsStringType[MeshData].as_outlet(id='meshes')

    Storage: MapsStringType stores Map[str, T] with unwrapped elements

    Hooks: Uses default implementations from IType
    - _validate_port_type: Allows all port types (inlet, outlet, config)
    - _configure_port: No special configuration needed
    """

    field_class: "Optional[Type[DataField]]" = None  # Will be set to MapsStringField after it's defined

    # No hook overrides needed - uses defaults from IType!
    # Allows inlets, outlets, and configs
    # No special port configuration

    @property
    def value(self):
        """MapsStringType don't have instances - this is for type checking only"""
        raise NotImplementedError("MapsStringType is a type descriptor, not instantiable")


# ============================================================================
# FIELD DEFINITION
# ============================================================================


@dataclass
class MapsStringField(DataField):
    """
    Field implementation for MapsStringType.

    Stores map of unwrapped values with element type tracking.

    Storage: Dict[str, T] where T is unwrapped (42.0 not FLOAT(42.0))
    Worker Access: Dict[str, T] (unwrapped primitives or instances)
    Transfer: Dict[str, T] (unwrapped)
    """

    _items: Dict[str, Any] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self):
        """Initialize complex field with default instance"""
        super().__post_init__()

        # Initialize from default
        initial_dict = self.default_kwargs.get("value", {})
        self._items = initial_dict

    def _get_own(self) -> Dict[str, Any]:
        """Return a copy of the map."""
        return dict(self._items)

    def _set_own(self, value: Any) -> None:
        """Store a string-keyed map.

        Raises:
            TypeError: If *value* is not a dict.
        """
        if not isinstance(value, dict):
            raise TypeError(f"MapsStringField requires dict, got {value.__class__.__name__}")
        self._items = value

    def reset(self) -> None:
        """Reset to default array"""
        initial_dict = self.default_kwargs.get("value", {})
        self._items = initial_dict
        self.is_dirty = True

    def has_data(self) -> bool:
        """Check if has any items"""
        return len(self._items) > 0

    def _own_to_dict(self) -> dict:
        """Return ``{"value": {key: item}}`` with each item as a field of the element type saves it."""
        # A compound's element is always an IType; `type | None` covers PrimitiveType[T].
        element = cast("Type[IType]", self.type_cls.element_type_cls)
        return {"value": {key: element_to_dict(element, item) for key, item in self._items.items()}}

    def _own_from_dict(self, data: dict) -> None:
        """Restore the items from ``_own_to_dict`` output."""
        # A compound's element is always an IType; `type | None` covers PrimitiveType[T].
        element = cast("Type[IType]", self.type_cls.element_type_cls)
        self._items = {key: element_from_dict(element, item) for key, item in data.get("value", {}).items()}

    # ========================================================================
    # ARRAY-SPECIFIC HELPERS
    # ========================================================================

    def get_item(self, index: str) -> Any:
        """Get specific item by index"""
        return self._items[index]

    def __len__(self) -> int:
        """Get array length"""
        return len(self._items)


# Set field_class now that MapsStringField is defined
MapsStringType.field_class = MapsStringField
