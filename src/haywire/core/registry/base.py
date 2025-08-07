"""
Base classes for the Haywire library system
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class LibraryMetadata:
    """Metadata for a Haywire library"""
    name: str
    version: str
    description: str
    url: str
    help_url: str
    author: str
    author_url: str
    dependencies: list[str] = None
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


class BaseRegistry(ABC):
    """Abstract base class for all registries"""
    
    def __init__(self):
        self._items: Dict[str, Any] = {}
        self._metadata: Dict[str, Dict[str, Any]] = {}
    
    def register(self, name: str, item: Any, metadata: Optional[Dict[str, Any]] = None):
        """Register an item with optional metadata"""
        self._items[name] = item
        if metadata:
            self._metadata[name] = metadata
    
    def get(self, name: str) -> Optional[Any]:
        """Get an item by name"""
        return self._items.get(name)
    
    def has(self, name: str) -> bool:
        """Check if an item is registered"""
        return name in self._items
    
    def list_names(self) -> list[str]:
        """List all registered item names"""
        return list(self._items.keys())
    
    def get_metadata(self, name: str) -> Optional[Dict[str, Any]]:
        """Get metadata for an item"""
        return self._metadata.get(name)


class BaseLibrary(ABC):
    """Abstract base class for all libraries"""
    
    def __init__(self, metadata: LibraryMetadata):
        self.metadata = metadata
    
    @abstractmethod
    def register_components(self, widget_registry, gadgets_registry, adapter_registry, node_registry):
        """Register this library's components with the global registries"""
        pass
    
    @abstractmethod
    def validate(self) -> bool:
        """Validate that this library is properly structured"""
        pass
