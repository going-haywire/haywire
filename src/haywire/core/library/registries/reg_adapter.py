import inspect
from typing import Optional, TypeVar, Union

from haywire.core.adapter.base_adapter import BaseAdapter
from ..library_identity import LibraryIdentity
from ..class_registry import BaseClassRegistry


class AdapterRegistry(BaseClassRegistry):
    """Registry for type conversion adapters"""

    def __init__(self):
        super().__init__()
        # Key: (source_type, target_type), Value: adapter_class
        self._adapters: dict[tuple[str, str], type[BaseAdapter]] = {}

    def _class_filter(self, cls):
        """Check if a class is a valid Haywire adapter class."""
        try:
            return (inspect.isclass(cls) and
                    issubclass(cls, BaseAdapter) and
                    cls != BaseAdapter and
                    hasattr(cls, 'class_identity'))
        except TypeError:
            return False

    def _register(self, adapter_cls: type[BaseAdapter], library_identity: Optional[LibraryIdentity] = None) -> str | None:
        """
        Register adapter class.
        Args:
            adapter_class: The adapter class to register.
            metadata: Optional metadata for the adapter.
        Returns:
            str: The haywire registry_key of the registered adapter.
        """
        source_key = adapter_cls.class_identity.converts_from
        target_key = adapter_cls.class_identity.converts_to

        key = (source_key, target_key)

        self._adapters[key] = adapter_cls

        # Register with base registry for metadata tracking
        registry_key = f"{source_key}_to_{target_key}"

        return super()._register(registry_key, adapter_cls, library_identity)

    def _unregister(self, registry_key: str) -> type[BaseAdapter] | None:
        """ Unregister an adapter by its haywire name.

        Args:
            adapter_name: The haywire name of the adapter to unregister
        """
        adapter_class = self.get(registry_key)
        key = next((k for k, cls in self._adapters.items() if cls.__name__ == adapter_class.__name__), None)
        del self._adapters[key]

        return super()._unregister(registry_key)
   
    def has_adapter(self, source_type: str, target_type: str) -> bool:
        """Check if an adapter exists for the given type conversion"""
        return (source_type, target_type) in self._adapters

    def get_adapter(self, source_type: str, target_type: str) -> type[BaseAdapter] | None:
        """Get adapter class for converting between two data types"""
        return self._adapters.get((source_type, target_type))

    def list_conversions(self) -> list[tuple[str, str]]:
        """List all available type conversions"""
        return list(self._adapters.keys())

    def can_connect(self, source_field: str, target_field: str) -> bool:
        """
        Check if two data fields can be connected.
        Returns True if types match or an adapter exists.
        """
        # Direct type match
        if source_field == target_field:
            return True

        # Check if adapter exists
        return self.has_adapter(source_field, target_field)