"""
Base classes and decorators for custom data types in Haywire.

Custom types enable libraries to define domain-specific data structures
that can be passed between nodes with type safety and serialization support.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable, Type, TypeVar, Union

from ..library.base_identity import BaseIdentity
from ..library.utils import derive_library_id, reg_key

T = TypeVar('T')


@dataclass
class CustomTypeIdentity(BaseIdentity):
    """
    Identity information for custom data types.
    
    Attributes:
        registry_id: Unique identifier within the library (inherited)
        registry_key: Full unique key including library ID (inherited)
        label: Human-readable display name (inherited)
        description: What this type represents (inherited)
        color: Color for UI representation (hex format)
        icon: Icon name for UI representation
        help_url: URL to documentation for this custom type
    """
    # Inherited from BaseIdentity:
    # - registry_id: str
    # - registry_key: str  
    # - label: str
    # - description: str
    
    # CustomType-specific fields:
    color: str = '#f1f1f1'
    icon: str = 'box'
    help_url: str = ''
    _cls: Type = None  # Reference to the decorated class. Set automatically.
    
    def to_spec(self, **overrides):
        """
        Generate DataPortSpec for this custom type.
        
        Args:
            **overrides: Additional keyword arguments to override spec fields
            
        Returns:
            DataPortSpec configured for this custom type
        """
        from ..data.specs import DataPortSpec
        from ..data.enums import ContainerType
        
        return DataPortSpec(
            id=self.registry_id,
            key=self.registry_key,
            cls_type=self._cls, 
            container_type=ContainerType.SINGLE,
            label=self.label,
            description=self.description,
            color=self.color,
            icon=self.icon,
            default=None,  # Custom types don't have default values
            **overrides
        )


def custom_type(cls: Type[T] = None, /, **kwargs) -> Union[Type[T], Callable[[Type[T]], Type[T]]]:
    """
    Decorator to register a class as a Haywire custom type.
    
    This decorator creates a CustomTypeIdentity for the class and validates that
    it has the required serialization methods.
    
    Args:
        registry_id (str, optional): Unique identifier within the library.
            Defaults to class name if not provided.
        registry_key (str, optional): Full registry key (library + type ID).
            Auto-derived from library ID and registry_id by the decorator.
        label (str, optional): Human-readable display name.
            Defaults to class name if not provided.
        description (str, optional): What this type represents.
            Defaults to empty string.
        color (str, optional): Color for UI representation (hex format).
            Defaults to '#f1f1f1'.
        icon (str, optional): Icon name for UI representation.
            Defaults to 'box'.
        help_url (str, optional): URL to documentation.
            Defaults to empty string.
    
    Usage:
        @custom_type(label="3D Mesh", description="Polygonal mesh data")
        @dataclass
        class MeshData:
            vertices: list[tuple[float, float, float]]
            faces: list[tuple[int, int, int]]
            
            def to_dict(self) -> dict:
                return asdict(self)
            
            @classmethod
            def from_dict(cls, data: dict) -> 'MeshData':
                return cls(**data)
    
    Raises:
        TypeError: If class doesn't have required to_dict/from_dict methods
    """
    def decorator(inner_cls: Type[T]) -> Type[T]:
        # Validate required methods
        if not hasattr(inner_cls, 'to_dict'):
            raise TypeError(
                f"@custom_type requires 'to_dict(self) -> dict' method on {inner_cls.__name__}"
            )
        if not hasattr(inner_cls, 'from_dict'):
            raise TypeError(
                f"@custom_type requires 'from_dict(cls, data: dict)' class method on {inner_cls.__name__}"
            )
        
        # Set defaults from class name if not provided
        kwargs.setdefault('registry_id', inner_cls.__name__)
        kwargs.setdefault('label', inner_cls.__name__)
        
        # Auto-derive registry_key if not explicitly set
        if 'registry_key' not in kwargs:
            library_id = derive_library_id(inner_cls)
            kwargs['registry_key'] = reg_key(library_id, kwargs['registry_id'])
        
        # Add the class reference
        kwargs['_cls'] = inner_cls
        
        # Attach identity to class
        inner_cls.class_identity = CustomTypeIdentity(**kwargs)
        
        # Auto-generate and attach specs
        inner_cls.specs = inner_cls.class_identity.to_spec()
        
        return inner_cls
    
    return decorator if cls is None else decorator(cls)
