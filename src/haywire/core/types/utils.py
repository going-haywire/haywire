from typing import TYPE_CHECKING, Any, Dict, Optional, Type, TypeVar
from dataclasses import asdict
from cattrs.preconf.json import make_converter
from haywire.core.types.registry import TypeRegistry
from haywire.ui.widget.globals import validate_widget_type_compatibility


from .interface import IType

if TYPE_CHECKING:
    from .ports import DataPort


T = TypeVar('T')

# Create a reusable JSON-compatible converter
_json_converter = make_converter()

def is_cattrs_serializable(value: Any) -> tuple[bool, str | None]:
    """
    Check if a value is serializable using cattrs (JSON-compatible).
    
    Args:
        value: Value to check
        
    Returns:
        Tuple of (is_serializable, error_message)
    """
    try:
        # Try to unstructure and then dumps to JSON
        unstructured = _json_converter.unstructure(value)
        _json_converter.dumps(unstructured)
        return (True, None)
    except Exception as e:
        return (False, str(e))
    
# ============================================================================
# SHARED VALIDATION UTILITIES
# ============================================================================


def normalize_and_validate_default(
    default_value: Any,
    cls: type[IType],
    context: str = "type decorator"
) -> Dict[str, Any]:
    """
    Normalize and validate default value for type registration or port creation.
    
    For PrimitiveTypes: Auto-wraps primitive values into {'value': ...}
    For all types: Validates serializability with cattrs
    
    Args:
        default_value: The default value (can be primitive or dict)
        cls: The type class being validated
        context: Description of where this is being called from (for error messages)
        
    Returns:
        Normalized default dict
        
    Raises:
        TypeError: If default is not serializable or invalid format
        
    Examples:
        normalize_and_validate_default(0.0, FLOAT, "@type decorator")
        # Returns: {'value': 0.0}
        
        normalize_and_validate_default({'vertices': []}, MeshData, "as_inlet")
        # Returns: {'vertices': []}
    """
    from .base import PrimitiveType

    # Already a dict - use as-is
    if isinstance(default_value, dict):
        normalized = default_value

    # we dont want the user to use instances.
    # we want the user to supply constructor kwargs, not instances
    elif isinstance(default_value, IType):
        raise TypeError(
            f"{context} for {cls.__name__}: 'default' must be a dict "
            f"of constructor kwargs. Got {type(default_value).__name__}(). "
        )

    # we only allow this simplification for PrimitiveType subclasses
    # Primitive value for PrimitiveType - auto-wrap
    elif issubclass(cls, PrimitiveType):
        normalized = {'value': default_value}

    # Complex type with non-dict default - error
    else:
        raise TypeError(
            f"{context} for {cls.__name__}: 'default' must be a dict "
            f"of constructor kwargs. Got {type(default_value).__name__}. "
            f"Only PrimitiveType subclasses can use primitive values directly."
        )
    
    # Validate serializability
    serializable, error_msg = is_cattrs_serializable(normalized)
    if not serializable:
        raise TypeError(
            f"{context} for {cls.__name__}: 'default' must be cattrs/JSON serializable. "
            f"Got {normalized!r} which is not serializable: {error_msg}\n"
            f"For complex types, consider using None placeholders: default={{'value': None}} "
            f"and override create_default()."
        )
    
    return normalized


"""
Utility functions for type system.
"""

def create_port_from_type(
    type_cls: type['IType'],
    port_cls: type['DataPort'],
    id: str,
    **kwargs
) -> 'DataPort':
    """
    Create a DataPort from a type.
    
    Handles both simple types (FLOAT, MeshData) and compound types 
    (ArrayType, PooledType). The field is created automatically in 
    port.__post_init__ via type.create_field().
    
    Args:
        type_cls: Type class (FLOAT, ArrayType, etc.)
        port_cls: Port class (PortInlet or PortOutlet)
        id: Port identifier
        element_type_cls: For compound types, the element type
        **kwargs: Additional port attributes
    
    Returns:
        Configured DataPort (PortInlet or PortOutlet)
    
    Examples:
        # Simple type
        port = create_port_from_type(
            FLOAT, PortInlet, 'value', default=0.0
        )
        
        # Nested compound type
        port = create_port_from_type(
            PooledType, PortInlet, 'data',
            element_type_cls=ArrayType[STRING],
            default=[[...], [...]]
        )
    """
    from haywire.core.types.base import CompoundType

    element_type_cls: Optional[Type[IType]] = None

    # Validate element_type_cls for compound types
    if issubclass(type_cls, CompoundType):
        if type_cls.element_type_cls:
            if issubclass(type_cls.element_type_cls, IType):
                element_type_cls = type_cls.element_type_cls
        if not element_type_cls:
            raise ValueError(
                f"CompoundType {type_cls.__name__} requires "
                f"element_type_cls. Use parameterized syntax: "
                f"{type_cls.__name__}[ElementType].as_inlet(...)"
            )
    
    # Extract default for field creation
    default_override = kwargs.pop('default', None)
    
    # Merge identity from type
    port_kwargs = {
        **asdict(type_cls.class_identity),
        'id': id,
        'type_cls': type_cls,
        **kwargs  # User overrides
    }
        
    # Create port
    port = port_cls(**port_kwargs)
    
    # Store default override for field creation in __post_init__
    if default_override is not None:
        if isinstance(default_override, dict):
            port._default_override = default_override
        else:
            port._default_override = {'value': default_override}
    
    # Store creation recipe for serialization
    if (
        hasattr(type_cls, 'class_identity') 
        and type_cls.class_identity.registry_key
    ):
        recipe = {
            'registry_key': type_cls.class_identity.registry_key,
            'method': (
                'as_inlet' 
                if port_cls.__name__ == 'PortInlet' 
                else 'as_outlet'
            ),
            'kwargs': {
                'id': id,
                **{k: v for k, v in kwargs.items()}
            }
        }
        
        # Add default to recipe
        if default_override is not None:
            recipe['kwargs']['default'] = default_override
        
        # NEW: Recursive element type serialization
        if element_type_cls:
            recipe['element_type'] = _serialize_type_spec(element_type_cls)
        
        port._creation_recipe = recipe
    
    return port


def _serialize_type_spec(type_cls: type['IType']) -> dict:
    """
    Recursively serialize a type specification.
    
    Handles nested compound types like PooledType[ArrayType[STRING]].
    
    Args:
        type_cls: Type class to serialize
    
    Returns:
        Dict representing the type hierarchy
    
    Examples:
        _serialize_type_spec(STRING)
        # → {'registry_key': 'core.string'}
        
        _serialize_type_spec(ArrayType[STRING])
        # → {
        #     'registry_key': 'core.array',
        #     'element_type': {'registry_key': 'core.string'}
        #   }
        
        _serialize_type_spec(PooledType[ArrayType[STRING]])
        # → {
        #     'registry_key': 'core.pooled',
        #     'element_type': {
        #         'registry_key': 'core.array',
        #         'element_type': {'registry_key': 'core.string'}
        #     }
        #   }
    """
    from haywire.core.types.base import CompoundType
    
    if not hasattr(type_cls, 'class_identity'):
        raise ValueError(
            f"Type {type_cls.__name__} has no class_identity. "
            f"Was it decorated with @type?"
        )
    
    registry_key = type_cls.class_identity.registry_key
    if not registry_key:
        raise ValueError(
            f"Type {type_cls.__name__} has no registry_key"
        )
    
    spec = {'registry_key': registry_key}
    
    # Recursively handle compound types
    if (
        issubclass(type_cls, CompoundType) 
        and hasattr(type_cls, 'element_type_cls') 
        and type_cls.element_type_cls
    ):
        spec['element_type'] = _serialize_type_spec(
            type_cls.element_type_cls
        )
    
    return spec


def _deserialize_type_spec(spec: dict, type_registry: TypeRegistry) -> type['IType']:
    """
    Recursively deserialize a type specification.
    
    Args:
        spec: Serialized type specification
        type_registry: TypeRegistry to look up types
    
    Returns:
        Reconstructed type class (possibly parameterized)
    
    Examples:
        _deserialize_type_spec(
            {'registry_key': 'core.string'}, 
            registry
        )
        # → STRING
        
        _deserialize_type_spec(
            {
                'registry_key': 'core.pooled',
                'element_type': {
                    'registry_key': 'core.array',
                    'element_type': {'registry_key': 'core.string'}
                }
            },
            registry
        )
        # → PooledType[ArrayType[STRING]]
    """
    registry_key = spec['registry_key']
    
    # Get base type class
    type_cls = type_registry.get_type_class(registry_key)
    if not type_cls:
        raise ValueError(
            f"Type '{registry_key}' not found in registry"
        )
    
    # Recursively handle element type
    if 'element_type' in spec:
        element_type_cls = _deserialize_type_spec(
            spec['element_type'], 
            type_registry
        )
        # Parameterize: ArrayType[STRING]
        return type_cls[element_type_cls]
    
    # Simple type
    return type_cls
