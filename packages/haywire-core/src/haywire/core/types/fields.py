"""
DataField Classes - Storage and management for node port data

This module provides the complete DataField hierarchy for storing and managing
data in node ports. Each field type handles a specific storage pattern with
uniform API for different access scenarios.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Generic, TypeVar, cast

from haywire.core.types import IType, BaseType, PrimitiveType, Event


T = TypeVar("T")

# ============================================================================
# BASE DATAFIELD
# ============================================================================


@dataclass
class DataField(ABC, Generic[T]):
    """
    Abstract base class for all data field types.

    DataFields store data in their natural form and provide uniform
    access patterns for different use cases:
    - Node-to-node data transfer
    - Worker method access
    - Edge validation

    Each IType declares which DataField class handles its storage.

    Type tracking via element_type_cls:
    - PrimitiveField: element_type_cls = Python type (float, str, etc.)
    - BaseField: element_type_cls = BaseType class (MeshData, etc.)
    - CompoundField: element_type_cls = IType of elements (FLOAT, MeshData)
    """

    type_cls: type[IType]  # Type class (FLOAT, MeshData, ArrayType, etc.)
    default_kwargs: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize event system"""
        self.on_changed: Event[Any] = Event[Any]()
        self.is_dirty: bool = True

    # ========================================================================
    # CORE API - Implemented by each subclass
    # ========================================================================

    @abstractmethod
    def get_value(self) -> T:
        """
        Get value for worker/binding access.

        Returns data in most convenient form:
        - PrimitiveField: Unwrapped primitive (42.0)
        - BaseField: BaseType instance (MeshData(...))
        - CompoundField: Container (dict, list, etc.)
        """
        pass

    @abstractmethod
    def set_value(self, value: Any, source_id: str | None = None) -> None:
        """
        Set value from connection or programmatic update.

        Handles both wrapped (IType instances) and unwrapped values.

        Args:
            value: Can be IType instance or raw value
            source_id: Required for PooledField, ignored for others
        """
        pass

    def get_stored_type(self) -> type[IType]:
        """
        Return the type stored in this field.

        This method allows fields to declare what type they store
        because in some cases this differs from the type the field is
        created from.
        EdgeWrapper uses this to evaluate compatibility and
        which types to pass to AdapterFactory for chain creation.

        Returns:
            type[IType]: The IType class of the instance(s) that is(are) actually stored.
        """
        return self.type_cls

    @abstractmethod
    def reset(self) -> None:
        """Reset field to default value"""
        pass

    @abstractmethod
    def has_data(self) -> bool:
        """Check if field has any data"""
        pass

    def remove_source(self, source_id: str) -> None:
        """Remove a disconnected source."""
        pass

    # ========================================================================
    # EVENT SYSTEM
    # ========================================================================

    def add_observer(self, callback: Callable) -> None:
        """Add observer for value changes"""
        self.on_changed.append(callback)

    def remove_observer(self, callback: Callable) -> None:
        """Remove observer"""
        self.on_changed.remove(callback)

    def fire(self, value: Any) -> None:
        """Notify observers of change"""
        self.on_changed(value)

    def mark_clean(self) -> None:
        """Mark field as clean (up-to-date)"""
        self.is_dirty = False

    # ========================================================================
    # SERIALIZATION - Stub methods for field value persistence
    # ========================================================================

    def to_dict(self) -> dict:
        """
        Serialize field value.

        Default stub implementation - returns decorator default.
        Subclasses override for actual serialization.

        Returns:
            dict: Serialized representation
        """
        # Default: return decorator default
        if hasattr(self.type_cls, "class_identity"):
            default_dict = getattr(self.type_cls.class_identity, "default", None)
            if isinstance(default_dict, dict):
                return default_dict
        return {}

    def from_dict(self, data: dict) -> None:
        """
        Deserialize field value.

        Default stub implementation - resets to default.
        Subclasses override for actual deserialization.

        Args:
            data: Dictionary containing serialized value
        """
        # Default: reset to initial state
        self.reset()


# ============================================================================
# PRIMITIVEFIELD - Stores unwrapped primitives
# ============================================================================


@dataclass
class PrimitiveField(DataField[T]):
    """
    Stores unwrapped primitive value for maximum performance.

    Storage: T (unwrapped primitive - 42.0 not FLOAT(42.0))
    Worker Access: T (unwrapped primitive)
    Transfer: T (unwrapped primitive)

    Key insight: We store the primitive directly, not wrapped in PrimitiveType.
    Type information comes from type_cls, not from wrapping every value.

    """

    _value: T = field(init=False, repr=False)
    _default: T = field(init=False, repr=False)

    def __post_init__(self):
        """Initialize primitive field with default value"""
        super().__post_init__()

        # Extract and store unwrapped primitive
        self._default = self.default_kwargs.get("value")
        self._value = self._default

    def get_value(self) -> T:
        """Get unwrapped primitive - O(1) direct access"""
        return self._value

    def set_value(self, value: Any, source_id: str | None = None) -> None:
        """
        Store primitive value

        Accepts both wrapped (rare, from adapters) and unwrapped (common).

        Examples:
            field.set_value(42.0)           # From worker - stores 42.0
            field.set_value(FLOAT(42.0))    # From adapter - unwraps to 42.0
        """

        self._value = value
        self.is_dirty = True
        if self.on_changed.has_observers():
            self.fire(self._value)

    def reset(self) -> None:
        """Reset to default value"""
        self._value = self._default
        self.is_dirty = True

    def has_data(self) -> bool:
        """Check if has data"""
        return self._value is not None

    # ========================================================================
    # SERIALIZATION - Delegate to PrimitiveType classmethods
    # ========================================================================

    def to_dict(self) -> dict:
        """
        Serialize primitive field value.

        Wraps the unwrapped value in a temporary type instance and calls
        the unified IType.to_dict() instance method.

        Returns:
            dict: Serialized representation
        """
        # PrimitiveField stores PrimitiveType[T] subclasses; cast to access
        # PrimitiveType's value= constructor.
        primitive_cls = cast("type[PrimitiveType[T]]", self.type_cls)
        return primitive_cls(value=self._value).to_dict()

    def from_dict(self, data: dict) -> None:
        """
        Deserialize primitive field value.

        Delegates to PrimitiveType.from_dict(data) classmethod.

        Args:
            data: Dictionary containing serialized value
        """
        self._value = self.type_cls.from_dict(data)
        self.is_dirty = True


# ============================================================================
# BASEFIELD - Stores BaseType instances
# ============================================================================


@dataclass
class BaseField(DataField[BaseType]):
    """
    Stores BaseType instance.

    Storage: BaseType instance (MeshData(...))
    Worker Access: BaseType instance
    Transfer: BaseType instance

    Complex types are already "unwrapped" - the instance IS the value.
    """

    _container: BaseType = field(init=False, repr=False)

    def __post_init__(self):
        """Initialize complex field with default instance"""
        super().__post_init__()

        self._container = self.type_cls(**self.default_kwargs)

    def get_value(self) -> BaseType:
        """Get instance"""
        return self._container

    def set_value(self, value: Any, source_id: str | None = None) -> None:
        """Store BaseType instance"""
        if not isinstance(value, self.type_cls):
            raise TypeError(f"Expected {self.type_cls.__name__}, got {type(value).__name__}")

        # type_cls is type[IType] at the base; for BaseField it's always type[BaseType].
        self._container = cast(BaseType, value)
        self.is_dirty = True
        if self.on_changed.has_observers():
            self.fire(self._container)

    def reset(self) -> None:
        """Reset to default value"""
        # type_cls is type[IType] at the base; for BaseField it's always type[BaseType].
        self._container = cast(BaseType, self.type_cls(**self.default_kwargs))
        self.is_dirty = True

    def has_data(self) -> bool:
        """Check if has data"""
        return self._container is not None

    # ========================================================================
    # SERIALIZATION - Delegate to BaseType methods
    # ========================================================================

    def to_dict(self) -> dict:
        """
        Serialize BaseType field value.

        Delegates to instance's to_dict() method.

        Returns:
            dict: Serialized representation
        """
        return self._container.to_dict()

    def from_dict(self, data: dict) -> None:
        """
        Deserialize BaseType field value.

        Delegates to type's from_dict(data) classmethod.

        Args:
            data: Dictionary containing serialized value
        """
        self._container = self.type_cls.from_dict(data)
        self.is_dirty = True


# Set field_class attributes after classes are defined
PrimitiveType.field_class = PrimitiveField
BaseType.field_class = BaseField
