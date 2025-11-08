"""
Registry for managing custom data types.

This module provides the CustomTypeRegistry class which handles registration,
validation, and retrieval of custom data types defined by libraries.
"""

import inspect
from typing import Type, Any

from ...types.base_type import CustomTypeIdentity
from ..class_registry import BaseClassRegistry
from ..library_identity import LibraryIdentity


class CustomTypeRegistry(BaseClassRegistry):
    """
    Registry for managing custom data types.
    
    Custom types are library-defined data structures that can be passed between
    nodes through inlet/outlet connections. They must implement to_dict() and
    from_dict() methods for serialization.
    """

    def __init__(self):
        super().__init__()

    def _class_filter(self, cls) -> bool:
        """
        Check if a class is a valid custom type.
        
        A valid custom type must:
        - Be a class
        - Have a class_identity attribute
        - Have class_identity be a CustomTypeIdentity instance
        - Have to_dict method
        - Have from_dict class method
        
        Args:
            cls: The class to check
            
        Returns:
            True if the class is a valid custom type, False otherwise
        """
        try:
            # Must be a class
            if not inspect.isclass(cls):
                return False
            
            # Must have class_identity attribute
            if not hasattr(cls, 'class_identity'):
                return False
            
            # class_identity must be a CustomTypeIdentity
            if not isinstance(cls.class_identity, CustomTypeIdentity):
                return False
            
            # Must have required serialization methods
            if not hasattr(cls, 'to_dict'):
                return False
            if not hasattr(cls, 'from_dict'):
                return False
            
            return True
            
        except (TypeError, AttributeError):
            return False

    def _register_class(self, type_cls: type, library_identity: LibraryIdentity) -> str | None:
        """
        Register a custom type class with library metadata.
        
        Args:
            type_cls: The custom type class to register
            library_identity: Library metadata to associate with the type
            
        Returns:
            The registry_key of the registered type
            
        Raises:
            ValueError: If a type with the same key is already registered
        """
        # Use registry_key that was set by the decorator
        registry_key = type_cls.class_identity.registry_key
        
        # Register using parent class method
        return super()._register(registry_key, type_cls, library_identity)

    def _unregister_class(self, registry_key: str) -> type | None:
        """
        Unregister a custom type by its registry_key.
        
        Args:
            registry_key: The registry_key of the type to unregister
            
        Returns:
            The unregistered type class or None if not found
        """
        return super()._unregister(registry_key)

    def get_type_class(self, key: str) -> Type | None:
        """
        Get custom type class by registry key.
        
        Args:
            key: Registry key in format "library_id:type_name"
            
        Returns:
            The custom type class or None if not found
        """
        return self._classes.get(key)

    def validate_instance(self, key: str, instance: Any) -> bool:
        """
        Check if an instance is of a registered custom type.
        
        Args:
            key: Registry key of the custom type
            instance: Object instance to validate
            
        Returns:
            True if instance is of the specified type, False otherwise
        """
        type_cls = self.get_type_class(key)
        if type_cls is None:
            return False
        
        return isinstance(instance, type_cls)

    def create_instance_from_dict(self, key: str, data: dict) -> Any | None:
        """
        Create an instance of a custom type from serialized data.
        
        Args:
            key: Registry key of the custom type
            data: Dictionary containing serialized data
            
        Returns:
            New instance of the custom type or None if type not found
        """
        type_cls = self.get_type_class(key)
        if type_cls is None:
            return None
        
        try:
            return type_cls.from_dict(data)
        except Exception as e:
            # Log error but don't crash
            print(f"Error creating instance of {key} from dict: {e}")
            return None
