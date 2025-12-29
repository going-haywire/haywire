from typing import TYPE_CHECKING, Any, Dict, Optional, Type, TypeVar
from dataclasses import asdict
from cattrs.preconf.json import make_converter
from haywire.ui.widget.globals import validate_widget_type_compatibility

from .interface import IType

if TYPE_CHECKING:
    from haywire.core.types.ports import DataPort
    from haywire.core.types.interface import IType


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
    port_cls: type['DataPort'],  # PortInlet or PortOutlet
    id: str,
    element_type_cls: Optional[type['IType']] = None,
    **kwargs
) -> 'DataPort':
    """
    Create a DataPort from a type.
    
    Handles both simple types (FLOAT, MeshData) and compound types (ArrayType, PooledType).
    The field is created automatically in port.__post_init__ via type.create_field().
    
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
        port = create_port_from_type(FLOAT, PortInlet, 'value', default=0.0)
        
        # Compound type
        port = create_port_from_type(
            ArrayType, PortInlet, 'numbers',
            element_type_cls=FLOAT,
            default=[1.0, 2.0]
        )
    """
    from haywire.core.types.base import CompoundType
    # Validate element_type_cls for compound types
    if issubclass(type_cls, CompoundType):
        if not element_type_cls:
            raise ValueError(
                f"CompoundType {type_cls.__name__} requires element_type_cls. "
                f"Use parameterized syntax: {type_cls.__name__}[ElementType].as_inlet(...)"
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
    
    # Add element_type_cls if provided (must be before port creation)
    if element_type_cls:
        port_kwargs['element_type_cls'] = element_type_cls
    
    # Create port
    port = port_cls(**port_kwargs)
    
    # Store default override for field creation in __post_init__
    if default_override is not None:
        if isinstance(default_override, dict):
            port._default_override = default_override
        else:
            # Convert single value to dict
            port._default_override = {'value': default_override}
    
    # Store creation recipe for serialization
    if hasattr(type_cls, 'class_identity') and type_cls.class_identity.registry_key:
        recipe = {
            'registry_key': type_cls.class_identity.registry_key,
            'method': 'as_inlet' if port_cls.__name__ == 'PortInlet' else 'as_outlet',
            'kwargs': {
                'id': id,
                **{k: v for k, v in kwargs.items()}
            }
        }
        
        # Add default to recipe
        if default_override is not None:
            recipe['kwargs']['default'] = default_override
        
        # Add element type to recipe for compounds
        if element_type_cls and hasattr(element_type_cls, 'class_identity'):
            recipe['kwargs']['element_type_registry_key'] = element_type_cls.class_identity.registry_key
        
        port._creation_recipe = recipe
    
    # Field will be created in port.__post_init__ via type_cls.create_field()
    
    return port
