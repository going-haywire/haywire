from abc import ABC
from typing import Any, Dict, Optional
    
class BaseRegistry(ABC):
    """Abstract base class for all registries"""

    def __init__(self):
        self._items: Dict[str, Any] = {}

    def _register(self, name: str, item: Any) -> str | None:
        """Register an item with optional metadata"""
        self._items[name] = item
        return name

    def _unregister(self, name: str) -> type[Any]:
        """Remove an item from the registry"""
        delete_item = self._items.get(name)

        if name in self._items:
            del self._items[name]

        return delete_item

    def get(self, name: str) -> Optional[Any]:
        """Get an item by name"""
        return self._items.get(name)

    def has(self, name: str) -> bool:
        """Check if an item is registered"""
        return name in self._items

    def list_names(self) -> list[str]:
        """List all registered item names"""
        return list(self._items.keys())