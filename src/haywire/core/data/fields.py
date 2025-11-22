from __future__ import annotations
from typing import TYPE_CHECKING, Any, Callable, Dict, Generic, Optional, TypeVar
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

from .event import Event, T

T = TypeVar('T')

@dataclass
class DataField(ABC, Generic[T]):
    """
    Abstract base class for data fields with change notification.
    
    Generic over the value type T.
    """
    type_cls: type[T]  # The type class (e.g., FLOAT, MeshData)
    is_pooled: bool
    
    def __post_init__(self):
        self.on_changed: Event[Any] = Event[Any]()
        self.is_dirty: bool = True

    @abstractmethod
    def set_value(self, value: T, source_id: str | None = None):
        """Set value with optional source tracking"""
        pass
    
    @abstractmethod
    def get_value(self) -> T | Dict[str, T]:
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
    def reset(self):
        """Reset field to default value"""
        pass
    
    def add_observer(self, callback: Callable):
        self.on_changed.append(callback)
    
    def remove_observer(self, callback: Callable):
        self.on_changed.remove(callback)
    
    def fire(self):
        self.on_changed(self.get_value())
    
    def mark_clean(self):
        self.is_dirty = False


@dataclass
class SingleField(DataField[T]):
    """Single-value data field - stores one instance"""
    _value: T = field(init=False)
    _default: T = field(init=False)
    
    def __init__(self, type_cls: type[T], default_value: T):
        self.type_cls = type_cls
        self.is_pooled = False
        self._value = default_value
        self._default = default_value
        super().__post_init__()

    def set_value(self, value: T, source_id: str | None = None) -> None:
        if self._value != value:
            self._value = value
            self.is_dirty = True
            if source_id is None:
                self._default = value  # UI update changes default
            self.fire()
    
    def get_value(self) -> T:
        return self._value
    
    def remove_source(self, source_id: str):
        """Reset to default when source removed"""
        self._value = self._default
        self.is_dirty = True
        self.fire()
    
    def has_sources(self) -> bool:
        return self._value is not None
    
    def reset(self):
        self._value = self._default
        self.is_dirty = True


@dataclass
class PooledField(DataField[T]):
    """Pooled-value data field - stores dict of source_id -> instance"""
    _sources: Dict[str, T] = field(default_factory=dict, init=False)
    
    def __init__(self, type_cls: type[T]):
        self.type_cls = type_cls
        self.is_pooled = True
        self._sources = {}
        super().__post_init__()

    def set_value(self, value: T, source_id: str | None = None):
        if source_id is None:
            raise ValueError("source_id required for PooledField")
        if self._sources.get(source_id) != value:
            self._sources[source_id] = value
            self.is_dirty = True
            self.fire()
    
    def get_value(self) -> Dict[str, T]:
        """Return dict of all source values"""
        return dict(self._sources)
    
    def remove_source(self, source_id: str):
        if source_id in self._sources:
            del self._sources[source_id]
            self.is_dirty = True
            self.fire()
    
    def has_sources(self) -> bool:
        return len(self._sources) > 0
    
    def get_values_list(self) -> list[T]:
        return list(self._sources.values())
    
    def get_source_ids(self) -> list[str]:
        return list(self._sources.keys())
    
    def reset(self):
        self._sources.clear()
        self.is_dirty = True


