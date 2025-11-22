from typing import TYPE_CHECKING, Any, Callable, Type, TypeVar
import cattrs
from cattrs.preconf.json import make_converter


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
    cls: type,
    context: str = "type decorator"
) -> dict:
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
    from .base_type import PrimitiveType
    
    # Already a dict - use as-is
    if isinstance(default_value, dict):
        normalized = default_value
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