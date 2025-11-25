from typing import TYPE_CHECKING, Any, Dict, Type, TypeVar
from dataclasses import asdict
from cattrs.preconf.json import make_converter

from haywire.core.types.ports import DataPort, PortInlet
from haywire.core.ui.widget.globals import validate_widget_type_compatibility

from .interface import IType

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

def create_port_base(
    type_cls: Type[IType],
    port_class: DataPort,
    id: str,
    **kwargs
):
    """
    Shared logic for creating ports (inlets/outlets).
    
    This is internal - not meant to be called directly by users.
    """
    # Prepare kwargs with id
    kwargs['id'] = id
    
    # Normalize and validate default if provided
    if 'default' in kwargs:
        port_type = "inlet" if issubclass(port_class, PortInlet) else "outlet"
        kwargs['default'] = normalize_and_validate_default(
            kwargs['default'],
            type_cls,
            context=f"as_{port_type}('{id}')"
        )
    
    # Merge identity with overrides
    port_kwargs = {
        **asdict(type_cls.class_identity),
        **kwargs
    }
    
    widget = port_kwargs['widget']

    if widget:
        is_compatible, error_msg = validate_widget_type_compatibility(
            widget_registry_key=widget,
            type_cls=type_cls
        )
            
        if not is_compatible:
            raise TypeError(f"Invalid widget for port '{id}': {error_msg}")


    # Create the port
    port = port_class(**port_kwargs)
    
    # Set the library reference
    port.class_library = getattr(type_cls, 'class_library', None)
    
    # Remove default from kwargs for storage
    kwargs.pop('default', None)
    
    # Store creation recipe for serialization
    if type_cls.class_identity.registry_key and not type_cls.class_identity.registry_key.startswith('default:'):
        method_name = 'as_inlet' if port_class.__name__ == 'PortInlet' else 'as_outlet'
        port._creation_recipe = {
            'registry_key': type_cls.class_identity.registry_key,
            'method': method_name,
            'kwargs': kwargs
        }
    
    return port