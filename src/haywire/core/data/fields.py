"""
DataField Classes - Storage and management for node port data

This module provides the complete DataField hierarchy for storing and managing
data in node ports. Each field type handles a specific storage pattern with
uniform API for different access scenarios.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Dict, Generic, List, Optional, TypeVar

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
    
    DataFields store data in their natural form (not wrapped in IType containers)
    and provide uniform access patterns for different use cases:
    - Node-to-node data transfer
    - Worker method access
    - Widget property binding
    
    Each subclass handles a specific storage pattern:
    - PrimitiveField: Single primitive value wrapped in PrimitiveType
    - ComplexField: Single BaseType instance
    - PooledField: Dict of source_id -> unwrapped values
    - ArrayField: List of unwrapped values
    """
    
    type_cls: type[IType]           # Container type (FLOAT, MeshData, etc.)
    element_type_cls: type[IType]   # Element type (for arrays/pooled)
    is_pooled: bool
    is_array: bool
    
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
        Get value for worker access.
        
        Returns data in most convenient form for workers:
        - PrimitiveField: Unwrapped primitive (42.0, "hello")
        - ComplexField: BaseType instance (MeshData(...))
        - PooledField: Dict[str, T] or List[T]
        - ArrayField: List[T]
        """
        pass
    
    @abstractmethod
    def set_value(self, value: Any, source_id: str | None = None) -> None:
        """
        Set value from connection or programmatic update.
        
        Handles both wrapped (IType instances from connections) and
        unwrapped values (direct programmatic setting).
        
        Args:
            value: Can be IType instance (from connection) or raw value
            source_id: Required for PooledField, ignored for others
        """
        pass
    
    @abstractmethod
    def get_for_transfer(self) -> IType | List[IType]:
        """
        Get value wrapped in IType for node-to-node transfer.
        
        Returns:
            IType instance or list of IType instances ready to send
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
        
        Considers:
        - Direct type match
        - Available adapters
        - Adapter chains
        - Structural compatibility (single vs pooled vs array)
        
        Args:
            other_field: Source field to check compatibility with
            adapter_registry: Registry for looking up adapters
        
        Returns:
            (is_compatible, reason_or_adapter_chain)
            
        Examples:
            (True, "direct")  # Same type
            (True, "Temperature->FLOAT")  # Single adapter
            (True, "Temperature->FLOAT->STRING")  # Adapter chain
            (False, "No adapter found")  # Incompatible
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
# PRIMITIVEFIELD - Stores PrimitiveType[T] instances
# ============================================================================

@dataclass
class PrimitiveField(DataField[T]):
    """
    Stores single PrimitiveType instance (FLOAT, INT, STRING, etc.).
    
    Storage: PrimitiveType[T] instance (e.g., FLOAT(42.0))
    Worker Access: Unwrapped primitive (e.g., 42.0)
    Transfer: PrimitiveType instance (no re-wrapping needed)
    
    This avoids repeated instantiation - the wrapper is created once
    and its .value property is updated via the setter.
    """
    
    _container: PrimitiveType[T] = field(init=False, repr=False)
    _default_kwargs: Dict[str, Any] = field(default_factory=dict)
    
    def __init__(self, type_cls: type[PrimitiveType], default_kwargs: Dict[str, Any]):
        """
        Initialize primitive field.
        
        Args:
            type_cls: PrimitiveType class (FLOAT, INT, etc.)
            default_kwargs: Constructor kwargs (e.g., {'value': 42.0})
        """
        self.type_cls = type_cls
        self.element_type_cls = type_cls  # Same as type_cls for primitives
        self.is_pooled = False
        self.is_array = False
        
        self._default_kwargs = default_kwargs
        self._container = type_cls(**default_kwargs)
        
        super().__post_init__()
    
    def set_value(self, value: Any, source_id: str | None = None) -> None:
        """
        Set value from connection or programmatic update.
        
        Examples:
            field.set_value(FLOAT(42.0))  # From connection (already wrapped)
            field.set_value(42.0)         # Programmatic (auto-wrap)
        """
        if isinstance(value, self.type_cls):
            # Already wrapped - store directly
            self._container = value
        elif isinstance(value, IType):
            # Different IType - type mismatch
            raise TypeError(f"Expected {self.type_cls.__name__}, got {type(value).__name__}")
        else:
            # Raw primitive - wrap it
            self._container = self.type_cls(value=value)
        
        self.is_dirty = True
        self.fire(self._container)
    
    def get_value(self) -> T:
        """
        Get unwrapped primitive for worker access.
        
        Returns:
            42.0  # Unwrapped via .value property
        """
        return self._container.value
    
    def get_for_transfer(self) -> IType:
        """
        Get stored instance for transfer.
        
        Returns:
            FLOAT(42.0)  # The actual stored instance (efficient!)
        """
        return self._container
    
    def is_compatible_with(
        self, 
        other_field: DataField, 
        adapter_registry: 'AdapterRegistry'
    ) -> tuple[bool, str]:
        """
        Check type compatibility.
        
        Examples:
            FLOAT <- FLOAT: (True, "direct")
            FLOAT <- Temperature: (True, "Temperature->FLOAT")
            FLOAT <- STRING: (False, "No adapter found")
        """
        # Direct type match
        if other_field.type_cls == self.type_cls:
            return (True, "direct")
        
        # Check for single adapter
        if adapter_registry.has_adapter(other_field.type_cls, self.type_cls):
            adapter_chain = f"{other_field.type_cls.__name__}->{self.type_cls.__name__}"
            return (True, adapter_chain)
        
        # Check for adapter chain (multi-hop)
        chain = adapter_registry.find_adapter_chain(other_field.type_cls, self.type_cls)
        if chain:
            chain_str = "->".join([c.__name__ for c in chain])
            return (True, chain_str)
        
        return (False, f"No adapter from {other_field.type_cls.__name__} to {self.type_cls.__name__}")
    
    def reset(self) -> None:
        """Reset to default value"""
        self._container = self.type_cls(**self._default_kwargs)
        self.is_dirty = True
    
    def has_data(self) -> bool:
        """Check if has data"""
        return self._container is not None


# ============================================================================
# COMPLEXFIELD - Stores BaseType instances
# ============================================================================

@dataclass
class ComplexField(DataField[BaseType]):
    """
    Stores single BaseType instance (MeshData, custom dataclasses, etc.).
    
    Storage: BaseType instance (e.g., MeshData(vertices=[], faces=[]))
    Worker Access: Same BaseType instance
    Transfer: Same instance (no wrapping needed)
    
    Complex types are already "wrapped" - they are the data containers.
    """
    
    _container: BaseType = field(init=False, repr=False)
    _default_kwargs: Dict[str, Any] = field(default_factory=dict)
    
    def __init__(self, type_cls: type[BaseType], default_kwargs: Dict[str, Any]):
        """
        Initialize complex field.
        
        Args:
            type_cls: BaseType class (MeshData, etc.)
            default_kwargs: Constructor kwargs (e.g., {'vertices': [], 'faces': []})
        """
        self.type_cls = type_cls
        self.element_type_cls = type_cls  # Same as type_cls for complex types
        self.is_pooled = False
        self.is_array = False
        
        self._default_kwargs = default_kwargs
        self._container = type_cls(**default_kwargs)
        
        super().__post_init__()
    
    def set_value(self, value: Any, source_id: str | None = None) -> None:
        """
        Set BaseType instance from connection.
        
        Examples:
            field.set_value(MeshData(vertices=[...], faces=[...]))
        """
        if not isinstance(value, self.type_cls):
            raise TypeError(f"Expected {self.type_cls.__name__}, got {type(value).__name__}")
        
        self._container = value
        self.is_dirty = True
        self.fire(self._container)
    
    def get_value(self) -> BaseType:
        """
        Get instance for worker access.
        
        Returns:
            MeshData(vertices=[...], faces=[...])
        """
        return self._container
    
    def get_for_transfer(self) -> IType:
        """
        Get instance for transfer.
        
        Returns:
            MeshData(...)  # The actual instance (no wrapping needed)
        """
        return self._container
    
    def is_compatible_with(
        self, 
        other_field: DataField, 
        adapter_registry: 'AdapterRegistry'
    ) -> tuple[bool, str]:
        """
        Check type compatibility (same logic as PrimitiveField).
        """
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
# POOLEDFIELD - Stores Dict[str, T]
# ============================================================================

@dataclass
class PooledField(DataField[Dict[str, T]]):
    """
    Stores dict of source_id -> unwrapped values (multi-source inlet).
    
    Storage: Dict[str, T] where T is unwrapped primitive or BaseType
    Worker Access: Dict or list of unwrapped values
    Transfer: Not allowed (inlet-only)
    
    Used when a node needs to aggregate data from multiple upstream nodes.
    Each source is tracked by its node ID, allowing updates/removals.
    """
    
    _sources: Dict[str, T] = field(default_factory=dict, init=False, repr=False)
    
    def __init__(self, element_type_cls: type[IType]):
        """
        Initialize pooled field.
        
        Args:
            element_type_cls: Type of elements in the pool (FLOAT, MeshData, etc.)
        """
        # Pooled uses a synthetic type_cls as marker
        self.type_cls = type('PooledType', (BaseType,), {})
        self.element_type_cls = element_type_cls
        self.is_pooled = True
        self.is_array = False
        
        self._sources = {}
        
        super().__post_init__()
    
    def set_value(self, value: Any, source_id: str | None = None) -> None:
        """
        Set value from a specific source.
        
        Examples:
            field.set_value(FLOAT(42.0), source_id="node1")
            # Stores: {"node1": 42.0}
            
            field.set_value(FLOAT(15.0), source_id="node2")
            # Stores: {"node1": 42.0, "node2": 15.0}
            
            field.set_value(FLOAT(99.0), source_id="node1")
            # Stores: {"node1": 99.0, "node2": 15.0}  # Overwrites node1
        """
        if source_id is None:
            raise ValueError("PooledField requires source_id")
        
        # Unwrap value based on type
        if isinstance(value, PrimitiveType):
            unwrapped = value.value
        elif isinstance(value, BaseType):
            unwrapped = value  # Keep complex types as-is
        else:
            unwrapped = value
        
        # Check if value actually changed
        if self._sources.get(source_id) == unwrapped:
            return
        
        # Update source
        self._sources[source_id] = unwrapped
        self.is_dirty = True
        self.fire(dict(self._sources))
    
    def get_value(self) -> Dict[str, T]:
        """
        Get dict of all source values.
        
        Returns:
            {"node1": 42.0, "node2": 15.0}  # Primitives unwrapped
            or
            {"node1": MeshData(...), "node2": MeshData(...)}  # Complex as-is
        """
        return dict(self._sources)
    
    def get_for_transfer(self) -> IType:
        """
        Not allowed - pooled fields are inlet-only.
        """
        raise RuntimeError(
            "PooledField cannot be used with outlets. "
            "Pooled fields are for aggregating multiple inputs only."
        )
    
    def is_compatible_with(
        self, 
        other_field: DataField, 
        adapter_registry: 'AdapterRegistry'
    ) -> tuple[bool, str]:
        """
        Check if incoming field's element type is compatible.
        
        Examples:
            Pooled[FLOAT] <- FLOAT: (True, "direct")
            Pooled[FLOAT] <- Temperature: (True, "Temperature->FLOAT")
            Pooled[FLOAT] <- Pooled[FLOAT]: (False, "Cannot connect pooled to pooled")
            Pooled[FLOAT] <- Array[FLOAT]: (False, "Cannot pool arrays")
        """
        # Cannot receive from another pooled field
        if other_field.is_pooled:
            return (False, "Cannot connect pooled to pooled")
        
        # Cannot receive arrays
        if other_field.is_array:
            return (False, "Cannot pool array outputs")
        
        # Check element type compatibility
        if other_field.element_type_cls == self.element_type_cls:
            return (True, "direct")
        
        if adapter_registry.has_adapter(other_field.element_type_cls, self.element_type_cls):
            return (True, f"{other_field.element_type_cls.__name__}->{self.element_type_cls.__name__}")
        
        chain = adapter_registry.find_adapter_chain(other_field.element_type_cls, self.element_type_cls)
        if chain:
            return (True, "->".join([c.__name__ for c in chain]))
        
        return (False, f"No adapter from {other_field.element_type_cls.__name__} to {self.element_type_cls.__name__}")
    
    def reset(self) -> None:
        """Clear all sources"""
        self._sources.clear()
        self.is_dirty = True
    
    def has_data(self) -> bool:
        """Check if has any sources"""
        return len(self._sources) > 0
    
    # ========================================================================
    # POOLED-SPECIFIC HELPERS
    # ========================================================================
    
    def remove_source(self, source_id: str) -> None:
        """
        Remove a disconnected source.
        
        Args:
            source_id: Node ID to remove
        """
        if source_id in self._sources:
            del self._sources[source_id]
            self.is_dirty = True
            self.fire(dict(self._sources))
    
    def get_values_list(self) -> List[T]:
        """
        Get values as list (for iteration).
        
        Returns:
            [42.0, 15.0]
        """
        return list(self._sources.values())
    
    def get_source_ids(self) -> List[str]:
        """
        Get list of source node IDs.
        
        Returns:
            ["node1", "node2"]
        """
        return list(self._sources.keys())


# ============================================================================
# ARRAYFIELD - Stores List[T]
# ============================================================================

@dataclass
class ArrayField(DataField[List[T]]):
    """
    Stores list of unwrapped values (homogeneous, typed).
    
    Storage: List[T] where T is unwrapped primitive or BaseType
    Worker Access: Same list of unwrapped values
    Transfer: List of wrapped IType instances
    
    Used for typed arrays like Array[FLOAT] or Array[MeshData].
    Elements are stored unwrapped for efficiency.
    """
    
    _items: List[T] = field(default_factory=list, init=False, repr=False)
    _default_kwargs: Dict[str, Any] = field(default_factory=dict)
    
    def __init__(self, element_type_cls: type[IType], default_kwargs: Dict[str, Any]):
        """
        Initialize array field.
        
        Args:
            element_type_cls: Type of array elements (FLOAT, MeshData, etc.)
            default_kwargs: Constructor kwargs (e.g., {'value': [1.0, 2.0, 3.0]})
        """
        # Array uses a synthetic type_cls as marker
        self.type_cls = type('ArrayType', (BaseType,), {})
        self.element_type_cls = element_type_cls
        self.is_pooled = False
        self.is_array = True
        
        self._default_kwargs = default_kwargs
        
        # Initialize from default
        initial_list = default_kwargs.get('value', [])
        self._items = self._unwrap_items(initial_list)
        
        super().__post_init__()
    
    def _unwrap_items(self, items: List[Any]) -> List[T]:
        """
        Helper to unwrap list items if they're IType instances.
        
        Args:
            items: List that may contain IType instances or raw values
            
        Returns:
            List of unwrapped values
        """
        result = []
        for item in items:
            if isinstance(item, PrimitiveType):
                result.append(item.value)  # Unwrap primitive
            else:
                result.append(item)  # Already unwrapped
        return result
    
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
            
            # Complex types:
            field.set_value([MeshData(...), MeshData(...)])
            # Stored: [MeshData(...), MeshData(...)]
        """
        if not isinstance(value, list):
            raise TypeError(f"ArrayField requires list, got {type(value).__name__}")
        
        self._items = self._unwrap_items(value)
        self.is_dirty = True
        self.fire(list(self._items))
    
    def get_value(self) -> List[T]:
        """
        Get list for worker access.
        
        Returns:
            [42.0, 3.14, 27.5]  # Primitives unwrapped
            or
            [MeshData(...), MeshData(...)]  # Complex types as-is
        """
        return list(self._items)
    
    def get_for_transfer(self) -> List[IType]:
        """
        Get list wrapped for transfer.
        
        Re-wraps primitives, keeps complex types as-is.
        
        Returns:
            [FLOAT(1.0), FLOAT(2.0), FLOAT(3.0)]  # Primitives re-wrapped
            or
            [MeshData(...), MeshData(...)]  # Complex types as-is
        """
        # Re-wrap primitives, keep complex types as-is
        if issubclass(self.element_type_cls, PrimitiveType):
            return [self.element_type_cls(value=item) for item in self._items]
        else:
            return list(self._items)  # Already BaseType instances
    
    def is_compatible_with(
        self, 
        other_field: DataField, 
        adapter_registry: 'AdapterRegistry'
    ) -> tuple[bool, str]:
        """
        Check if incoming array has compatible element type.
        
        Examples:
            Array[FLOAT] <- Array[FLOAT]: (True, "direct")
            Array[FLOAT] <- Array[Temperature]: (True, "Array[Temperature->FLOAT]")
            Array[FLOAT] <- FLOAT: (False, "Cannot connect single to array")
        """
        # Must be array to array
        if not other_field.is_array:
            return (False, "Cannot connect non-array to array inlet")
        
        # Check element type compatibility
        if other_field.element_type_cls == self.element_type_cls:
            return (True, "direct")
        
        if adapter_registry.has_adapter(other_field.element_type_cls, self.element_type_cls):
            return (True, f"Array[{other_field.element_type_cls.__name__}->Array[{self.element_type_cls.__name__}]")
        
        chain = adapter_registry.find_adapter_chain(other_field.element_type_cls, self.element_type_cls)
        if chain:
            chain_str = "->".join([c.__name__ for c in chain])
            return (True, f"Array[{chain_str}]")
        
        return (False, f"No adapter from Array[{other_field.element_type_cls.__name__}] to Array[{self.element_type_cls.__name__}]")
    
    def reset(self) -> None:
        """Reset to default array"""
        initial_list = self._default_kwargs.get('value', [])
        self._items = self._unwrap_items(initial_list)
        self.is_dirty = True
    
    def has_data(self) -> bool:
        """Check if has any items"""
        return len(self._items) > 0
    
    # ========================================================================
    # ARRAY-SPECIFIC HELPERS
    # ========================================================================
    
    def get_item(self, index: int) -> T:
        """
        Get specific item by index.
        
        Args:
            index: Item index
            
        Returns:
            Item at index (unwrapped)
        """
        return self._items[index]
    
    def __len__(self) -> int:
        """Get array length"""
        return len(self._items)