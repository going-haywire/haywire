"""
Array Compound Type - Final Simplified Version

Key changes:
1. Uses hooks from IType (_validate_port_type, _configure_port)
2. No special port attribute setting (uses defaults from CompoundType)
3. Clean and minimal - just declares field_class
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, List, Optional, Type, TypeVar

from haywire.core.types import type, FlowType, DataField, CompoundType

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
    It inherits the element type's flow type (if it is set).
    !!Setting the flow type in the decorator or as_inlet/as_outlet has no effect!!

    Hooks: Uses default implementations from IType
    - _validate_port_type: Allows all port types (inlet, outlet, config)
    - _configure_port: Sets flow type based on element type
    """

    field_class: "Optional[Type[DataField]]" = None  # Will be set to ArrayField after it's defined

    # Allows inlets, outlets, and configs

    @classmethod
    def _configure_port(cls, port, **context) -> None:
        """
        array type's flow type is determined by its element type

        Override:
        - Set flow type based on element type.
        - Set color based on element type.
        """
        # array type's flow type is determined by its element type
        if not port.type_cls.element_type_cls:
            return

        # Start with the immediate element type
        current_type = port.type_cls.element_type_cls

        # Drill down until we find a non-NONE flow type
        while current_type is not None:
            # Check if this type has a non-NONE flow type
            if hasattr(current_type, "class_identity"):
                if current_type.class_identity.flow_type != FlowType.NONE:
                    port.flow_type = current_type.class_identity.flow_type
                    port.color = current_type.class_identity.color
                    if port.flow_type == FlowType.CONTROL:
                        raise ValueError("ArrayType cannot have CONTROL flow type based on its element type")
                    if port.flow_type == FlowType.CALLBACK:
                        raise ValueError(
                            "ArrayType cannot have CALLBACK flow type based on its element type"
                        )
                    return

                # Move to next level if available
                if hasattr(current_type, "element_type_cls"):
                    current_type = current_type.element_type_cls
                else:
                    break

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

    def get_value(self) -> List[Any]:
        """
        Get list for worker access.

        Returns:
            [42.0, 3.14, 27.5]  # Primitives unwrapped
            or
            [MeshData(...), MeshData(...)]  # Complex types as-is
        """
        return list(self._items)

    def set_value(self, value: Any, source_id: str | None = None) -> None:
        """
        Set array from connection or programmatic update.

        Examples:
            # From connection (list of instances):
            field.set_value([FLOAT(1), FLOAT(2), FLOAT(3)])
            # Stored: [1.0, 2.0, 3.0]

            # Programmatic (already unwrapped):
            field.set_value([1.0, 2.0, 3.0])
            # Stored: [1.0, 2.0, 3.0]
        """
        if not isinstance(value, list):
            raise TypeError(f"ArrayField requires list, got {value.__class__.__name__}")

        self._items = value
        self.is_dirty = True
        if self.on_changed.has_observers():
            self.fire(list(self._items))

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
