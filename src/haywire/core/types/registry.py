"""
Registry for managing all data types.

This module provides the TypeRegistry class which handles registration,
validation, and retrieval of all data types (type variants and custom compound types).
"""

import inspect
from typing import Type, Any

from .interface import IType
from .identity import DataTypeIdentity
from ..registry.base import BaseRegistry
from ..library.identity import LibraryIdentity


class TypeRegistry(BaseRegistry):
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
            
            # Must inherit from IType
            if not issubclass(cls, IType):
                return False
            
            # Must have class_identity attribute
            if not hasattr(cls, 'class_identity'):
                return False
            
            # class_identity must be a DataPortIdentity
            if not isinstance(cls.class_identity, DataTypeIdentity):
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
    
    def get_identity(self, key: str) -> DataTypeIdentity | None:
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
        
        #identity = type_cls.class_identity
               
        # For custom compound types, check direct isinstance
        return isinstance(instance, type_cls)

    def resolve_type_from_spec(self, spec: dict) -> Type['IType']:
        """
        Resolve a type spec to a fully parameterized type class.
        
        Handles nested compound types like PooledType[ArrayType[STRING]].
        
        Args:
            spec: Dict with 'registry_key' and optional 'element_type'
        
        Returns:
            Resolved type class, parameterized if compound
        
        Examples:
            registry.resolve_type_from_spec({'registry_key': 'core.float'})
            # → FLOAT
            
            registry.resolve_type_from_spec({
                'registry_key': 'core.array',
                'element_type': {'registry_key': 'core.string'}
            })
            # → ArrayType[STRING]
            
            registry.resolve_type_from_spec({
                'registry_key': 'core.pooled',
                'element_type': {
                    'registry_key': 'core.array',
                    'element_type': {'registry_key': 'core.string'}
                }
            })
            # → PooledType[ArrayType[STRING]]
        """
        registry_key = spec.get('registry_key')
        if not registry_key:
            raise ValueError("Spec missing 'registry_key'")
        
        type_cls = self.get_type_class(registry_key)
        if not type_cls:
            raise ValueError(f"Type '{registry_key}' not found in registry")
        
        # Recursively resolve element type for compounds
        if 'element_type' in spec:
            element_type_cls = self.resolve_type_from_spec(spec['element_type'])
            return type_cls[element_type_cls]
        
        return type_cls

