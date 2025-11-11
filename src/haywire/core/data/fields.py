from __future__ import annotations
from typing import Any, Callable, Set, List
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

from .enums import DataType, DataContainerType
from .event import Event, T


@dataclass
class DataField(ABC):
    """
    Abstract base class for data fields with change notification.
    
    The type field accepts DataType enum, string (registry_key for custom types),
    or None. Enum values are automatically converted to strings in __post_init__.
    
    Attributes:
        type: DataType enum, registry_key string (e.g., 'core:float', 'mylib:mesh'), or None
        value: The current value
        is_pooled: Whether this field accepts multiple input sources
    """
    type: str | DataType | None
    value: T 
    is_pooled: bool

    def __post_init__(self):
        # Convert DataType enum to string for uniform handling
        if isinstance(self.type, DataType):
            self.type = self.type.value
        # type can be: string (enum value or registry_key) or None (for custom types)

        self._default_value: T = self.value
        self.on_changed: Event[T] = Event[T]()
        self.is_dirty: bool = True

    @abstractmethod
    def set_value(self, value: Any, source_id: str | None = None):
        """Set value with optional source tracking"""
        pass
    
    @abstractmethod
    def get_value(self):
        """Get the current value"""
        pass
    
    @abstractmethod
    def remove_source(self, source_id: str):
        """Remove a source connection"""
        pass
    
    @abstractmethod
    def has_sources(self) -> bool:
        """Check if field has any active sources"""
        pass
    
    @abstractmethod
    def get_values_list(self) -> list[Any]:
        """Get values as list"""
        pass
    
    @abstractmethod
    def get_source_ids(self) -> list[str]:
        """Get all source IDs (empty for scalar fields)"""
        pass
    
    def add_observer(self, callback: Callable):
        """Add a callback for value changes"""
        self.on_changed.append(callback)
    
    def remove_observer(self, callback: Callable):
        """Remove a callback for value changes"""
        self.on_changed.remove(callback)
    
    def fire(self):
        """Notify all observers of value change"""
        self.on_changed(self.value)
    
    def mark_clean(self):
        """Mark field as clean after processing"""
        self.is_dirty = False

    def reset(self):
        """Reset field to default value"""
        self.value = self._default_value
        self.is_dirty = True    
    
    def to_dict(self) -> dict:
        """Convert to dict for serialization"""
        return {
            'type': self.type.value if hasattr(self.type, 'value') else self.type,
            'container': self.container.value if hasattr(self.container, 'value') else self.container,
            'value': self._default_value,
            'is_dirty': self.is_dirty,
            'is_pooled': self.is_pooled,
        }


@dataclass
class SingleField(DataField):
    """Single-value data field"""

    def __post_init__(self):
        super().__post_init__()
        self.is_pooled = False

    def set_value(self, value: Any, source_id: str | None = None) -> None:
        """Set single value (source_id is ignored for scalar fields)"""
        if self.value != value:
            self.value = value
            self.is_dirty = True
            if source_id is None:
                # if the value is set via UI, it is the default value   
                self._default_value = value
            self.fire()
    
    def get_value(self):
        """Get the current value"""
        return self.value
    
    def remove_source(self, source_id: str):
        """Remove source - for scalar fields, set back to default value"""
        self.value = self._default_value
        self.is_dirty = True    
        self.fire()
    
    def has_sources(self) -> bool:
        """Check if field has a value"""
        return self.value is not None
    
    def get_values_list(self) -> list[Any]:
        """Get values as list"""
        return [self.value] if self.value is not None else []
    
    def get_source_ids(self) -> list[str]:
        """Get all source IDs (empty for scalar fields)"""
        return []
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for serialization"""
        result = super().to_dict()
        return result


@dataclass
class PooledField(DataField):
    """Pooled-value data field for many-to-one connections"""
    _aggregated_value: Any = field(default=None, init=False, repr=False)

    def __post_init__(self):
        super().__post_init__()
        self.is_pooled = True

    def set_value(self, value: Any, source_id: str | None = None):
        """Set value from a specific source"""
        if source_id is None:
            raise ValueError("source_id required for PooledField")
        if self.value.get(source_id) != value:
            self.value[source_id] = value
            self._aggregated_value = None  # Invalidate cache
            self.is_dirty = True
            self.fire()
    
    def get_value(self):
        """Get aggregated value as dict"""
        if self._aggregated_value is None:
            self._aggregated_value = dict(self.value)
        return self._aggregated_value
    
    def remove_source(self, source_id: str):
        """Remove a specific source"""
        if source_id in self.value:
            del self.value[source_id]
            self._aggregated_value = None
            self.is_dirty = True
            self.fire()
    
    def has_sources(self) -> bool:
        """Check if field has any sources"""
        return len(self.value) > 0
    
    def get_values_list(self) -> List[Any]:
        """Get values as list"""
        return list(self.value.values())
    
    def has_source(self, source_id: str) -> bool:
        """Check if a specific source exists"""
        return source_id in self.value
    
    def get_source_ids(self) -> List[str]:
        """Get all source IDs"""
        return list(self.value.keys())
    
    def clear_sources(self):
        """Clear all sources"""
        if self.value:
            self.value.clear()
            self._aggregated_value = None
            self.is_dirty = True
            self.fire()
    
    def to_dict(self) -> dict:
        """Convert to dict for serialization"""
        result = super().to_dict()
        result['is_pooled'] = True
        return result
