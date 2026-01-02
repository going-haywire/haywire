"""
DataField Classes - Storage and management for node port data

This module provides the complete DataField hierarchy for storing and managing
data in node ports. Each field type handles a specific storage pattern with
uniform API for different access scenarios.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import (
    TYPE_CHECKING, 
    Any, 
    Callable, 
    Dict, 
    Generic, 
    List, 
    Optional, 
    TypeVar
)

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
    
    def get_compatible_type(self) -> IType:
        """
        Return the type needed for adapter compatibility checking.
        
        This method allows fields to declare what type they need from
        the outlet for compatibility. EdgeWrapper uses this to evaluate 
        compatibility and which types to pass to AdapterFactory 
        for chain creation.
                    
        Returns:
            type: The IType class needed for compatibility
            
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

    """
    
    _value: T = field(init=False, repr=False)
    _default: T = field(init=False, repr=False)
    
    def __post_init__(self):
        """Initialize primitive field with default value"""
        super().__post_init__()
        
        # Extract and store unwrapped primitive
        self._default = self.default_kwargs.get('value')
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
        self.fire(self._value)
        
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
        
        self._container = value
        self.is_dirty = True
        self.fire(self._container)
       
    def reset(self) -> None:
        """Reset to default value"""
        self._container = self.type_cls(**self.default_kwargs)
        self.is_dirty = True
    
    def has_data(self) -> bool:
        """Check if has data"""
        return self._container is not None


# Set field_class attributes after classes are defined
PrimitiveType.field_class = PrimitiveField
BaseType.field_class = BaseField