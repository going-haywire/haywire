from typing import Optional, TypeVar, Union

from haywire.core.adapter.base_adapter import BaseAdapter, is_adapter
from ..library_identity import LibraryIdentity
from ..base import BaseClassRegistry, FileChangeEvent, FileEventType, RegistryFolder


class AdapterRegistry(BaseClassRegistry):
    """Registry for type conversion adapters"""
    directory_name: str = RegistryFolder.ADAPTERS.value
    class_filter = lambda self, cls: is_adapter(cls)  # Use the adapter filter

    def __init__(self):
        super().__init__()
        # Key: (source_type, target_type), Value: adapter_class
        self._adapters: dict[tuple[str, str], type[BaseAdapter]] = {}

    def _register(self, adapter_cls: type[BaseAdapter], library_itentity: Optional[LibraryIdentity] = None):
        """
        Register adapter class.
        Args:
            adapter_class: The adapter class to register.
            metadata: Optional metadata for the adapter.
        """
        # Store the library metadata and registry key as class attributes 
        # This will be used as the default for new instances
        adapter_cls.class_library = library_itentity

        source_key = adapter_cls.class_identity.converts_from
        target_key = adapter_cls.class_identity.converts_to

        key = (source_key, target_key)

        self._adapters[key] = adapter_cls

        # Register with base registry for metadata tracking
        registry_key = f"{source_key}_to_{target_key}"

        # Set the registry_key in the class_identity if it exists
        if hasattr(adapter_cls, 'class_identity'):
            adapter_cls.class_identity.registry_key = registry_key

        super()._register(registry_key, adapter_cls)

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