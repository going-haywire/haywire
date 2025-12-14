"""
DataField Classes - Storage and management for node port data

This module provides the complete DataField hierarchy for storing and managing
data in node ports. Each field type handles a specific storage pattern with
uniform API for different access scenarios.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Dict, Generic, List, TypeVar

from haywire.core.types.base import PrimitiveType

if TYPE_CHECKING:
    from haywire.core.adapter.registry import AdapterRegistry

from haywire.core.data.event import Event
from haywire.core.types.interface import IType
from haywire.core.types.base import BaseType


T = TypeVar('T')

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
    - Connection validation
    
    Each IType declares which DataField class handles its storage.
    
    Type tracking via element_type_cls:
    - PrimitiveField: element_type_cls = Python type (float, str, etc.)
    - BaseField: element_type_cls = BaseType class (MeshData, etc.)
    - CompoundField: element_type_cls = IType of elements (FLOAT, MeshData)
    """
    
    type_cls: type[IType]           # Type class (FLOAT, MeshData, ArrayType, etc.)
    element_type_cls: type[IType]   # For hierarchical type inspection
    
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
    
    @abstractmethod
    def get_for_transfer(self) -> Any:
        """
        Get value for node-to-node transfer.
        
        Returns unwrapped values (primitives, instances, containers).
        Type information tracked via type_cls/element_type_cls.
        """
        pass
    
    @abstractmethod
    def is_compatible_with(
        self,
        other_field: 'DataField',
        adapter_registry: 'AdapterRegistry'
    ) -> tuple[bool, str]:
        """
        Check if this field can receive data from other_field.
        
        Returns:
            (is_compatible, reason_or_adapter_chain)
        """
        pass
    
    @abstractmethod
    def reset(self) -> None:
        """Reset field to default value"""
        pass
    
    @abstractmethod
    def has_data(self) -> bool:
        """Check if field has any data"""
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
    
    This eliminates instantiation overhead and simplifies the data model.
    """
    
    _value: T = field(init=False, repr=False)
    _default: T = field(init=False, repr=False)
    
    def __init__(self, type_cls: type[PrimitiveType], default_kwargs: Dict[str, Any]):
        """
        Initialize primitive field.
        
        Args:
            type_cls: PrimitiveType class (FLOAT, INT, etc.)
            default_kwargs: Constructor kwargs (e.g., {'value': 42.0})
        """
        self.type_cls = type_cls
        # Get element_type_cls from type (e.g., FLOAT.element_type_cls = float)
        self.element_type_cls = type_cls.element_type_cls
       
        # Extract and store unwrapped primitive
        self._default = default_kwargs.get('value')
        self._value = self._default
        
        super().__post_init__()
    
    def get_value(self) -> T:
        """Get unwrapped primitive - O(1) direct access"""
        return self._value
    
    def set_value(self, value: Any, source_id: str | None = None) -> None:
        """
        Store primitive value - NO INSTANTIATION overhead!
        
        Accepts both wrapped (rare, from adapters) and unwrapped (common).
        
        Examples:
            field.set_value(42.0)           # From worker - stores 42.0
            field.set_value(FLOAT(42.0))    # From adapter - unwraps to 42.0
        """
        # Unwrap if it's a PrimitiveType instance (rare case)
        if isinstance(value, PrimitiveType):
            self._value = value.value
        else:
            # Common case: raw primitive - ZERO OVERHEAD!
            self._value = value
        
        self.is_dirty = True
        self.fire(self._value)
    
    def get_for_transfer(self) -> T:
        """Return unwrapped primitive - O(1) direct access"""
        return self._value
    
    def is_compatible_with(
        self,
        other_field: DataField,
        adapter_registry: 'AdapterRegistry'
    ) -> tuple[bool, str]:
        """Check type compatibility"""
        # Direct type match
        if other_field.type_cls == self.type_cls:
            return (True, "direct")
        
        # Check for single adapter
        if adapter_registry.has_adapter(other_field.type_cls, self.type_cls):
            return (True, f"{other_field.type_cls.__name__}->{self.type_cls.__name__}")
        
        # Check for adapter chain
        chain = adapter_registry.find_adapter_chain(other_field.type_cls, self.type_cls)
        if chain:
            return (True, "->".join([c.__name__ for c in chain]))
        
        return (False, f"No adapter from {other_field.type_cls.__name__} to {self.type_cls.__name__}")
    
    def reset(self) -> None:
        """Reset to default value"""
        self._value = self._default
        self.is_dirty = True
    
    def has_data(self) -> bool:
        """Check if has data"""
        return self._value is not None


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
    _default_kwargs: Dict[str, Any] = field(default_factory=dict)
    
    def __init__(self, type_cls: type[BaseType], default_kwargs: Dict[str, Any]):
        """
        Initialize complex field.
        
        Args:
            type_cls: BaseType class (MeshData, etc.)
            default_kwargs: Constructor kwargs
        """
        self.type_cls = type_cls
        # Get element_type_cls from type (e.g., MeshData.element_type_cls = MeshData)
        self.element_type_cls = type_cls.element_type_cls
        
        self._default_kwargs = default_kwargs
        self._container = type_cls(**default_kwargs)
        
        super().__post_init__()
    
    def get_value(self) -> BaseType:
        """Get instance"""
        return self._container
    
    def set_value(self, value: Any, source_id: str | None = None) -> None:
        """Store BaseType instance"""
        if not isinstance(value, self.type_cls):
            raise TypeError(f"Expected {self.type_cls.__name__}, got {type(value).__name__}")
        
        self._container = value
        self.is_dirty = True
        self.fire(self._container)
    
    def get_for_transfer(self) -> BaseType:
        """Return instance (no wrapping needed)"""
        return self._container
    
    def is_compatible_with(
        self,
        other_field: DataField,
        adapter_registry: 'AdapterRegistry'
    ) -> tuple[bool, str]:
        """Check type compatibility"""
        if other_field.type_cls == self.type_cls:
            return (True, "direct")
        
        if adapter_registry.has_adapter(other_field.type_cls, self.type_cls):
            return (True, f"{other_field.type_cls.__name__}->{self.type_cls.__name__}")
        
        chain = adapter_registry.find_adapter_chain(other_field.type_cls, self.type_cls)
        if chain:
            return (True, "->".join([c.__name__ for c in chain]))
        
        return (False, f"No adapter from {other_field.type_cls.__name__} to {self.type_cls.__name__}")
    
    def reset(self) -> None:
        """Reset to default value"""
        self._container = self.type_cls(**self._default_kwargs)
        self.is_dirty = True
    
    def has_data(self) -> bool:
        """Check if has data"""
        return self._container is not None


# ============================================================================
# COMPOUNDFIELD - Base for collections (Array, Pooled, etc.)
# ============================================================================

@dataclass
class CompoundField(DataField, ABC):
    """
    Abstract base for compound/collection fields.
    
    All compound fields:
    - Track element_type_cls for type safety (the IType of elements)
    - Store unwrapped elements for performance
    - Implement collection-specific semantics
    
    Hierarchical type access:
        field.element_type_cls → FLOAT (IType)
        field.element_type_cls.element_type_cls → float (Python type)
    
    Subclasses:
    - ArrayField: List[T] with homogeneous elements
    - PooledField: Dict[str, T] with source tracking
    - SetField: Set[T] with unique elements (future)
    """
    
    # Compound fields always have element_type_cls set to IType
    element_type_cls: type[IType]
    
    @abstractmethod
    def _unwrap_value(self, value: Any) -> Any:
        """
        Unwrap a single value if it's an IType instance.
        
        Used when receiving values that might be wrapped.
        """
        pass


# Set field_class attributes after classes are defined
PrimitiveType.field_class = PrimitiveField
BaseType.field_class = BaseField