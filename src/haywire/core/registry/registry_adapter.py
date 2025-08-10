from typing import Optional

from haywire.core.adapter.base import BaseAdapter
from haywire.core.registry.base import BaseClassRegistry, LibraryMetadata, RegistryFolder


class AdapterRegistry(BaseClassRegistry):
    """Registry for type conversion adapters"""
    directory_name: str = RegistryFolder.ADAPTERS.value

    def __init__(self):
        super().__init__()
        # Key: (source_type, target_type), Value: adapter_class
        self._adapters: dict[tuple[str, str], type[BaseAdapter]] = {}

    def register_adapter(self, adapter_class: type[BaseAdapter], metadata: Optional[LibraryMetadata] = None):
        """
        Register a self-registering adapter class.

        The adapter class inherits from BaseAdapter which ensures source_type and target_type exist.
        """
        source_type = adapter_class.source_type
        target_type = adapter_class.target_type

        # Convert types to strings for consistent key format
        source_key = source_type if isinstance(source_type, str) else source_type.__name__ if hasattr(source_type, '__name__') else str(source_type)
        target_key = target_type if isinstance(target_type, str) else target_type.__name__ if hasattr(target_type, '__name__') else str(target_type)

        key = (source_key, target_key)
        self._adapters[key] = adapter_class

        # Register with base registry for metadata tracking
        adapter_name = f"{source_key}_to_{target_key}"
        super()._register(adapter_name, adapter_class)

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