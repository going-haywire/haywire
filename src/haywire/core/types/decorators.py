"""
Type Decorators - Decorators for defining Haywire data types.

This module provides decorators for creating Haywire data types:
- @primitive_type: For primitive type wrappers (FLOAT, INT, etc.) and their variants (Temperature)
- @compound_type: For custom data structures with serialization (MeshData, TestData)
- @type_: Legacy decorator (deprecated, use @primitive_type or @compound_type instead)
"""

from typing import Type, TypeVar, Callable, get_type_hints
from dataclasses import asdict

from .base import TypeBase, PrimitiveType
from .identity import DataPortIdentity
from ..data.enums import ContainerType, FlowType
from ..library.utils import derive_library_identity, reg_key

T = TypeVar('T')


def primitive_type(**kwargs) -> Callable[[Type[T]], Type[T]]:
    """
    Decorator for primitive type wrappers and their variants.
    
    Use this for:
    - Base primitive types that wrap Python built-ins (FLOAT wraps float, INT wraps int)
    - Derived type variants that inherit from primitives (Temperature extends FLOAT)
    
    The decorator now AUTO-DETECTS the cls parameter from the 'value' type annotation.
    Classes must define a single field 'value: T' where T is the wrapped type.
    
    Examples:
        # Base primitive type - cls auto-extracted from value annotation:
        @primitive_type(
            registry_id='float',
            color='#50b0ff',
            widget='core:widget:number.widget',
            default=0.0
        )
        @dataclass
        class FLOAT(PrimitiveType[float]):
            value: float  # cls=float extracted automatically
        
        # Derived variant - inherits value: float from FLOAT:
        @primitive_type(
            registry_id='temperature',
            widget='example:widget:temp.widget',
            ui={'properties': {'unit': '°C'}}
        )
        class Temperature(FLOAT):
            pass  # Inherits value: float and cls=float from FLOAT
    
    Args:
        registry_id (str, optional): Unique identifier within library.
        cls (type, optional): DEPRECATED - Now auto-extracted from 'value' annotation.
            Only use if you need to override the detected type.
        label (str, optional): Human-readable display name.
        description (str, optional): Type description.
        color (str, optional): UI pin color (hex).
        icon (str, optional): UI pin icon.
        widget (str, optional): Widget for editing values.
        ui (dict, optional): Additional UI properties.
        container_type (ContainerType, optional): SINGLE, LIST, DICT, etc.
        flow_type (FlowType, optional): DATA, CTRL, or NONE.
        default (any, optional): Default value.
        help_url (str, optional): Documentation URL.
    
    Returns:
        Decorated class with class_identity attribute
    
    Raises:
        TypeError: If class doesn't have 'value' annotation or has extra fields
        TypeError: If used on a compound type (has to_dict/from_dict)
    """
    def decorator(inner_cls: Type[T]) -> Type[T]:
        # Ensure inherits from PrimitiveType (or TypeBase for backward compat)
        if not issubclass(inner_cls, TypeBase):
            # Auto-add PrimitiveType as base
            inner_cls = type(
                inner_cls.__name__,
                (PrimitiveType, *inner_cls.__bases__),
                dict(inner_cls.__dict__)
            )
        
        # Check if this looks like a compound type (mistake!)
        if hasattr(inner_cls, 'to_dict') and hasattr(inner_cls, 'from_dict'):
            raise TypeError(
                f"Type {inner_cls.__name__} has to_dict/from_dict methods, "
                f"suggesting it's a compound type. Use @compound_type instead of @primitive_type."
            )
        
        # Get annotations for auto-extraction of cls
        try:
            all_annotations = get_type_hints(inner_cls)
        except Exception:
            # Fall back if get_type_hints fails (e.g., forward references)
            all_annotations = getattr(inner_cls, '__annotations__', {})
        
        # AUTO-EXTRACT cls from 'value' annotation (validation already done in __init_subclass__)
        if 'value' in all_annotations:
            kwargs['cls'] = all_annotations['value']
        
        # Check if this inherits from another Type (derived variant)
        parent_identity = None
        for base in inner_cls.__bases__:
            if base != TypeBase and base != PrimitiveType and issubclass(base, TypeBase):
                if hasattr(base, 'class_identity'):
                    parent_identity = base.class_identity
                    break
        
        is_derived = parent_identity is not None
        
        # Set defaults
        kwargs.setdefault('registry_id', inner_cls.__name__)
        kwargs.setdefault('label', inner_cls.__name__)
        kwargs.setdefault('description', inner_cls.__doc__ or '')
        
        if is_derived:
            # Derived variant: inherit parent identity, override specifics
            identity_dict = asdict(parent_identity)
            
            identity_dict.update({
                'registry_id': kwargs['registry_id'],
                'registry_key': '',
                'label': kwargs.get('label', inner_cls.__name__),
                'description': kwargs.get('description', identity_dict['description']),
            })
            
            # Override specific fields if provided
            for field in ['color', 'flow_type', 'icon', 'widget', 'help_url', 'default', 'container_type', 'ui', 'cls']:
                if field in kwargs:
                    identity_dict[field] = kwargs[field]
            
            identity_dict['_is_variant'] = True
            
        else:
            # Base primitive type: cls was auto-extracted from value annotation
            identity_dict = {
                'registry_id': kwargs['registry_id'],
                'registry_key': '',
                'label': kwargs['label'],
                'description': kwargs['description'],
                'cls': kwargs['cls'],  # Auto-extracted from value: T annotation
                'container_type': kwargs.get('container_type', ContainerType.SINGLE),
                'flow_type': kwargs.get('flow_type', FlowType.DATA),
                'default': kwargs.get('default', None),
                'color': kwargs.get('color', '#757575'),
                'icon': kwargs.get('icon', 'circle'),
                'widget': kwargs.get('widget', None),
                'ui': kwargs.get('ui', {}),
                'help_url': kwargs.get('help_url', ''),
                '_is_variant': True
            }
        
        # Get library identity (survives hot-reload)
        library_identity = derive_library_identity(inner_cls)
        
        # Set registry_key
        library_id = library_identity.id if library_identity else None
        identity_dict['registry_key'] = reg_key(library_id, 'type',identity_dict['registry_id'])
        
        # Create and attach identity and library
        inner_cls.class_identity = DataPortIdentity(**identity_dict)
        inner_cls.class_library = library_identity
        
        return inner_cls
    
    return decorator


def compound_type(**kwargs) -> Callable[[Type[T]], Type[T]]:
    """
    Decorator for custom compound data types with serialization.
    
    Use this for custom data structures that:
    - Store complex/structured data
    - Implement to_dict() and from_dict() for serialization
    - Are typically dataclasses
    
    Examples:
        @compound_type(
            registry_id='mesh_data',
            label='3D Mesh',
            description='Polygonal mesh with vertices and faces',
            color='#4CAF50',
            icon='cube'
        )
        @dataclass
        class MeshData(TypeBase):
            '''3D mesh data structure'''
            vertices: List[Tuple[float, float, float]] = field(default_factory=list)
            faces: List[Tuple[int, int, int]] = field(default_factory=list)
            
            def to_dict(self) -> dict:
                return asdict(self)
            
            @classmethod
            def from_dict(cls, data: dict) -> 'MeshData':
                return cls(**data)
    
    Args:
        registry_id (str, optional): Unique identifier within library.
        label (str, optional): Human-readable display name.
        description (str, optional): Type description.
        color (str, optional): UI pin color (hex).
        icon (str, optional): UI pin icon.
        widget (str, optional): Widget for editing values (usually None for compound types).
        ui (dict, optional): Additional UI properties.
        container_type (ContainerType, optional): SINGLE, LIST, DICT, etc.
        flow_type (FlowType, optional): DATA, CTRL, or NONE.
        default (any, optional): Default value (usually None for compound types).
        help_url (str, optional): Documentation URL.
    
    Returns:
        Decorated class with class_identity attribute
    
    Raises:
        TypeError: If class is missing to_dict or from_dict methods
        ValueError: If 'cls' parameter is provided (not needed for compound types)
    """
    def decorator(inner_cls: Type[T]) -> Type[T]:
        # Ensure inherits from TypeBase
        if not issubclass(inner_cls, TypeBase):
            inner_cls = type(
                inner_cls.__name__,
                (TypeBase, *inner_cls.__bases__),
                dict(inner_cls.__dict__)
            )
        
        # Validate serialization methods
        if not hasattr(inner_cls, 'to_dict'):
            raise TypeError(
                f"Compound type {inner_cls.__name__} must implement to_dict() method for serialization"
            )
        
        if not hasattr(inner_cls, 'from_dict'):
            raise TypeError(
                f"Compound type {inner_cls.__name__} must implement from_dict() classmethod for deserialization"
            )
        
        # Validate that cls is not provided (common mistake)
        if 'cls' in kwargs:
            raise ValueError(
                f"Compound type {inner_cls.__name__} should not specify 'cls' parameter. "
                f"The class itself will be used as cls automatically."
            )
        
        # Set defaults
        kwargs.setdefault('registry_id', inner_cls.__name__)
        kwargs.setdefault('label', inner_cls.__name__)
        kwargs.setdefault('description', inner_cls.__doc__ or '')
        
        # Build identity for compound type
        identity_dict = {
            'registry_id': kwargs['registry_id'],
            'registry_key': '',
            'label': kwargs['label'],
            'description': kwargs['description'],
            'cls': inner_cls,  # The custom class itself!
            'container_type': kwargs.get('container_type', ContainerType.SINGLE),
            'flow_type': kwargs.get('flow_type', FlowType.DATA),
            'default': kwargs.get('default', None),
            'color': kwargs.get('color', '#f1f1f1'),
            'icon': kwargs.get('icon', 'box'),
            'widget': kwargs.get('widget', None),
            'ui': kwargs.get('ui', {}),
            'help_url': kwargs.get('help_url', ''),
            '_is_variant': False,  # Compound types are not variants
        }
        
        # Get library identity (survives hot-reload)
        library_identity = derive_library_identity(inner_cls)
        
        # Set registry_key
        library_id = library_identity.id if library_identity else None
        identity_dict['registry_key'] = reg_key(library_id, 'type', identity_dict['registry_id'])
        
        # Create and attach identity and library
        inner_cls.class_identity = DataPortIdentity(**identity_dict)
        inner_cls.class_library = library_identity
        
        return inner_cls
    
    return decorator
