"""
Type Decorators - Universal decorator for all Haywire data types.

This module provides the @type_ decorator which handles:
- Base primitive types (FLOAT, INT, STRING, etc.)
- Derived type variants (Temperature extends FLOAT)
- Custom compound types (MeshData with serialization)
"""

from typing import Type, TypeVar, Callable
from dataclasses import asdict

from .base import TypeBase
from ..data.identity import DataPortIdentity
from ..data.enums import ContainerType, FlowType
from ..library.utils import derive_library_id, reg_key

T = TypeVar('T')


def type_(**kwargs) -> Callable[[Type[T]], Type[T]]:
    """
    Universal decorator for all Haywire data types.
    
    Automatically detects the type category and configures appropriately:
    - Base primitive types: Wraps Python primitives (int, float, str, etc.)
    - Derived type variants: Inherits and overrides parent identity
    - Custom compound types: Registers types with to_dict/from_dict serialization
    
    Examples:
        # Base primitive type:
        @type_(registry_id='float', cls=float, color='#50b0ff', widget='core:number.widget')
        class FLOAT(TypeBase):
            '''Float data type'''
            pass
        
        # Derived type variant:
        @type_(registry_id='temperature', widget='example:temp.widget', ui={'unit': '°C'})
        class Temperature(FLOAT):
            '''Temperature measurement - inherits float cls from FLOAT'''
            pass
        
        # Custom compound type:
        @type_(registry_id='mesh_data', label='3D Mesh', color='#4CAF50')
        @dataclass
        class MeshData(TypeBase):
            '''3D mesh data structure'''
            vertices: list
            faces: list
            
            def to_dict(self) -> dict:
                return asdict(self)
            
            @classmethod
            def from_dict(cls, data: dict) -> 'MeshData':
                return cls(**data)
    
    Args:
        registry_id (str, optional): Unique identifier within library.
            Defaults to class name if not provided.
        cls (type, optional): Python type for base types (int, float, str, etc.).
            Required for base types, inherited for derived types.
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
        ValueError: If base type doesn't specify 'cls' argument
        TypeError: If compound type missing to_dict/from_dict methods
    """
    def decorator(inner_cls: Type[T]) -> Type[T]:
        # Ensure inherits from TypeBase
        if not issubclass(inner_cls, TypeBase):
            # Auto-add TypeBase as base class
            inner_cls = type(
                inner_cls.__name__,
                (TypeBase, *inner_cls.__bases__),
                dict(inner_cls.__dict__)
            )
        
        # ═══════════════════════════════════════════════════════════
        # DETECTION: Determine what kind of type this is
        # ═══════════════════════════════════════════════════════════
        
        # Check if this inherits from another Type (derived type)
        parent_identity = None
        for base in inner_cls.__bases__:
            if base != TypeBase and issubclass(base, TypeBase):
                if hasattr(base, 'class_identity'):
                    parent_identity = base.class_identity
                    break
        
        is_derived = parent_identity is not None
        
        # Check if this is a custom compound type (has serialization)
        is_compound = (
            hasattr(inner_cls, 'to_dict') and 
            hasattr(inner_cls, 'from_dict')
        )
        
        # ═══════════════════════════════════════════════════════════
        # SET DEFAULTS
        # ═══════════════════════════════════════════════════════════
        
        kwargs.setdefault('registry_id', inner_cls.__name__)
        kwargs.setdefault('label', inner_cls.__name__)
        kwargs.setdefault('description', inner_cls.__doc__ or '')
        
        # ═══════════════════════════════════════════════════════════
        # BUILD IDENTITY BASED ON TYPE CATEGORY
        # ═══════════════════════════════════════════════════════════
        
        if is_derived:
            # ───────────────────────────────────────────────────────
            # DERIVED TYPE: Inherit parent identity, override specifics
            # ───────────────────────────────────────────────────────
            
            # Start with parent's identity as dict
            identity_dict = asdict(parent_identity)
            
            # Update with new registry IDs
            identity_dict.update({
                'registry_id': kwargs['registry_id'],
                'registry_key': '',  # Will be set below
                'label': kwargs.get('label', inner_cls.__name__),
                'description': kwargs.get('description', identity_dict['description']),
                # Inherit cls, container_type, default from parent
            })
            
            # Override specific fields if provided in kwargs
            for field in ['color', 'flow_type', 'icon', 'widget', 'help_url', 'default', 'container_type', 'ui']:
                if field in kwargs:
                    identity_dict[field] = kwargs[field]
            
            # Mark as variant (derived from primitive)
            identity_dict['_is_variant'] = True
            identity_dict['_base_identity'] = parent_identity
            
        elif is_compound:
            # ───────────────────────────────────────────────────────
            # CUSTOM COMPOUND TYPE: New type with serialization
            # ───────────────────────────────────────────────────────
            
            identity_dict = {
                'registry_id': kwargs['registry_id'],
                'registry_key': '',  # Will be set below
                'label': kwargs['label'],
                'description': kwargs['description'],
                'cls': inner_cls,  # The custom class itself!
                'container_type': kwargs.get('container_type', ContainerType.SINGLE),
                'flow_type': kwargs.get('flow_type', FlowType.DATA),
                'default': kwargs.get('default', None),  # Custom types usually None
                'color': kwargs.get('color', '#f1f1f1'),
                'icon': kwargs.get('icon', 'box'),
                'widget': kwargs.get('widget', None),
                'ui': kwargs.get('ui', {}),
                'help_url': kwargs.get('help_url', ''),
                '_is_variant': False,  # This is a compound type, not a variant
                '_base_identity': None,
            }
            
        else:
            # ───────────────────────────────────────────────────────
            # BASE PRIMITIVE TYPE: Must specify cls
            # ───────────────────────────────────────────────────────
            
            if 'cls' not in kwargs:
                raise ValueError(
                    f"Base type {inner_cls.__name__} requires 'cls' argument "
                    f"specifying the Python type (e.g., cls=float, cls=int, cls=str)"
                )
            
            identity_dict = {
                'registry_id': kwargs['registry_id'],
                'registry_key': '',  # Will be set below
                'label': kwargs['label'],
                'description': kwargs['description'],
                'cls': kwargs['cls'],  # Python primitive type
                'container_type': kwargs.get('container_type', ContainerType.SINGLE),
                'flow_type': kwargs.get('flow_type', FlowType.DATA),
                'default': kwargs.get('default', None),  # Will be auto-set by Identity.__post_init__
                'color': kwargs.get('color', '#757575'),
                'icon': kwargs.get('icon', 'circle'),
                'widget': kwargs.get('widget', None),
                'ui': kwargs.get('ui', {}),
                'help_url': kwargs.get('help_url', ''),
                '_is_variant': True,  # Base primitive is still a variant
                '_base_identity': None,
            }
        
        # ═══════════════════════════════════════════════════════════
        # FINALIZE: Set registry_key and create identity
        # ═══════════════════════════════════════════════════════════
        
        # Auto-derive registry_key from library context
        library_id = derive_library_id(inner_cls)
        identity_dict['registry_key'] = reg_key(library_id, identity_dict['registry_id'])
        
        # Create and attach identity
        inner_cls.class_identity = DataPortIdentity(**identity_dict)
        
        return inner_cls
    
    return decorator
