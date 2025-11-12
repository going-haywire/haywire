"""
Registry for managing all data types.

This module provides the TypeRegistry class which handles registration,
validation, and retrieval of all data types (type variants and custom compound types).
"""

import inspect
from typing import Type, Any

from ...types.base import TypeBase
from ...data.identity import DataPortIdentity
from ..class_registry import BaseClassRegistry
from ..library_identity import LibraryIdentity


class TypeRegistry(BaseClassRegistry):
    """
    Universal registry for all data types.
    
    Handles both:
    - Type variants: Primitive type wrappers (FLOAT, INT, Temperature)
    - Custom compound types: Complex data structures with serialization (MeshData)
    
    All types must:
    - Inherit from TypeBase
    - Have a class_identity attribute (DataPortIdentity)
    - Custom types must also have to_dict/from_dict methods
    """

    def __init__(self):
        super().__init__()

    def _class_filter(self, cls) -> bool:
        """
        Check if a class is a valid type (variant or custom).
        
        A valid type must:
        - Be a class
        - Inherit from TypeBase
        - Have a class_identity attribute
        - Have class_identity be a DataPortIdentity instance
        - If custom type (_is_variant=False): have to_dict/from_dict methods
        
        Args:
            cls: The class to check
            
        Returns:
            True if the class is a valid type, False otherwise
        """
        try:
            # Must be a class
            if not inspect.isclass(cls):
                return False
            
            # Must inherit from TypeBase
            if not issubclass(cls, TypeBase):
                return False
            
            # Must have class_identity attribute
            if not hasattr(cls, 'class_identity'):
                return False
            
            # class_identity must be a DataPortIdentity
            if not isinstance(cls.class_identity, DataPortIdentity):
                return False
            
            # If it's a custom compound type (not variant), must have serialization
            if not cls.class_identity._is_variant:
                if not hasattr(cls, 'to_dict') or not hasattr(cls, 'from_dict'):
                    return False
            
            return True
            
        except (TypeError, AttributeError):
            return False

    def _register_class(self, type_cls: type, library_identity: LibraryIdentity) -> str | None:
        """
        Register a type class with library metadata.
        
        Args:
            type_cls: The type class to register
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
        Unregister a type by its registry_key.
        
        Args:
            registry_key: The registry_key of the type to unregister
            
        Returns:
            The unregistered type class or None if not found
        """
        return super()._unregister(registry_key)

    def get_type_class(self, key: str) -> Type | None:
        """
        Get type class by registry key.
        
        Args:
            key: Registry key in format "library_id:type_name"
            
        Returns:
            The type class or None if not found
        """
        return self._classes.get(key)
    
    def get_identity(self, key: str) -> DataPortIdentity | None:
        """
        Get the DataPortIdentity for a registered type.
        
        Args:
            key: Registry key of the type
            
        Returns:
            DataPortIdentity or None if not found
        """
        type_cls = self.get_type_class(key)
        if type_cls and hasattr(type_cls, 'class_identity'):
            return type_cls.class_identity
        return None
    
    def is_variant(self, key: str) -> bool:
        """
        Check if a registered type is a variant (vs. custom compound type).
        
        Args:
            key: Registry key of the type
            
        Returns:
            True if variant (primitive wrapper), False if custom compound type
        """
        identity = self.get_identity(key)
        if identity:
            return identity._is_variant
        return False

    def validate_instance(self, key: str, instance: Any) -> bool:
        """
        Check if an instance is of a registered type.
        
        For type variants: checks against the primitive cls (int, float, etc.)
        For custom types: checks isinstance() of the custom class
        
        Args:
            key: Registry key of the type
            instance: Object instance to validate
            
        Returns:
            True if instance is of the specified type, False otherwise
        """
        type_cls = self.get_type_class(key)
        if type_cls is None:
            return False
        
        identity = type_cls.class_identity
        
        # For type variants, check against the primitive cls
        if identity._is_variant and identity.cls:
            return isinstance(instance, identity.cls)
        
        # For custom compound types, check direct isinstance
        return isinstance(instance, type_cls)

    def create_instance_from_dict(self, key: str, data: dict) -> Any | None:
        """
        Create an instance of a custom type from serialized data.
        
        Only works for custom compound types (not type variants).
        
        Args:
            key: Registry key of the custom type
            data: Dictionary containing serialized data
            
        Returns:
            New instance of the custom type or None if not applicable
        """
        type_cls = self.get_type_class(key)
        if type_cls is None:
            return None
        
        # Only custom compound types have deserialization
        if self.is_variant(key):
            return None
        
        try:
            return type_cls.from_dict(data)
        except Exception as e:
            # Log error but don't crash
            print(f"Error creating instance of {key} from dict: {e}")
            return None
    
    def serialize_instance(self, key: str, instance: Any) -> dict | None:
        """
        Serialize an instance of a custom type to a dictionary.
        
        Only works for custom compound types (not type variants).
        
        Args:
            key: Registry key of the custom type
            instance: Instance to serialize
            
        Returns:
            Dictionary representation or None if not applicable
        """
        type_cls = self.get_type_class(key)
        if type_cls is None:
            return None
        
        # Only custom compound types have serialization
        if self.is_variant(key):
            return None
        
        if not isinstance(instance, type_cls):
            return None
        
        try:
            return instance.to_dict()
        except Exception as e:
            print(f"Error serializing instance of {key}: {e}")
            return None
