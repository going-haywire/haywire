import inspect
from typing import Optional, TypeVar, Union, Type

from haywire.core.adapter.base_adapter import BaseAdapter
from ..library_identity import LibraryIdentity
from ..class_registry import BaseClassRegistry


class AdapterRegistry(BaseClassRegistry):
    """Registry for type conversion adapters"""

    def __init__(self):
        super().__init__()
        # Key: (source_type, target_type) as actual Python classes
        # Value: adapter_class
        self._adapters: dict[tuple[Type, Type], type[BaseAdapter]] = {}

    def _class_filter(self, cls):
        """Check if a class is a valid Haywire adapter class."""
        try:
            return (inspect.isclass(cls) and
                    issubclass(cls, BaseAdapter) and
                    cls != BaseAdapter and
                    hasattr(cls, 'class_identity'))
        except TypeError:
            return False

    def _register_class(self, adapter_cls: type[BaseAdapter], library_identity: Optional[LibraryIdentity] = None) -> str | None:
        """
        Register adapter class using actual Python class types as keys.
        
        Args:
            adapter_cls: The adapter class to register.
            library_identity: Optional library metadata for the adapter.
            
        Returns:
            str: The haywire registry_key of the registered adapter.
        """
        source_type = adapter_cls.class_identity.converts_from
        target_type = adapter_cls.class_identity.converts_to

        # Use actual class types as key for fast type-based lookup
        key = (source_type, target_type)
        self._adapters[key] = adapter_cls

        # Register with base registry using the auto-derived registry_key from decorator
        registry_key = adapter_cls.class_identity.registry_key

        return super()._register(registry_key, adapter_cls, library_identity)

    def _unregister_class(self, registry_key: str) -> type[BaseAdapter] | None:
        """
        Unregister an adapter by its registry_key.
        
        Args:
            registry_key: The haywire registry_key of the adapter to unregister
            
        Returns:
            type[BaseAdapter] | None: The unregistered adapter class or None if not found
        """
        adapter_class = self._classes.get(registry_key)
        if not adapter_class:
            return None
            
        # Find and remove from type-based adapter dict
        key = next((k for k, cls in self._adapters.items() if cls == adapter_class), None)
        if key:
            del self._adapters[key]

        return super()._unregister(registry_key)
   
    def has_adapter(self, source_type: Type, target_type: Type) -> bool:
        """
        Check if an adapter exists for the given type conversion.
        
        Args:
            source_type: Source Python class (int, float, str, CustomType, etc.)
            target_type: Target Python class (int, float, str, CustomType, etc.)
            
        Returns:
            bool: True if adapter exists
        """
        return (source_type, target_type) in self._adapters

    def get_adapter(self, source_type: Type, target_type: Type) -> type[BaseAdapter] | None:
        """
        Get adapter class for converting between two data types.
        
        Args:
            source_type: Source Python class (int, float, str, CustomType, etc.)
            target_type: Target Python class (int, float, str, CustomType, etc.)
            
        Returns:
            type[BaseAdapter] | None: Adapter class or None if not found
        """
        return self._adapters.get((source_type, target_type))

    def list_conversions(self) -> list[tuple[Type, Type]]:
        """
        List all available type conversions.
        
        Returns:
            list[tuple[Type, Type]]: List of (source_type, target_type) tuples
        """
        return list(self._adapters.keys())

    def can_connect(self, source_type: Type | None, target_type: Type | None) -> bool:
        """
        Check if two data types can be connected.
        Returns True if types match or an adapter exists.
        
        Args:
            source_type: Source Python class (int, float, str, CustomType, etc.)
            target_type: Target Python class (int, float, str, CustomType, etc.)
            
        Returns:
            bool: True if types are compatible (match or adapter exists)
        """
        # Direct type match
        if source_type == target_type:
            return True

        # Check if adapter exists
        return self.has_adapter(source_type, target_type)