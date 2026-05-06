from typing import Any, Dict, TypeVar
from typing_extensions import NotRequired, TypedDict
from dataclasses import asdict
from cattrs.preconf.json import make_converter

from haywire.core.types.enums import PortType


from .interface import IType


T = TypeVar("T")


# ============================================================================
# PORT SPECIFICATION - Declarative port creation
# ============================================================================


class ElementTypeSpec(TypedDict):
    """Recursive element type specification for compound types."""

    registry_key: str
    element_type: NotRequired["ElementTypeSpec"]


class PortSpec(TypedDict):
    """
    Specification for creating a port.

    This is what as_inlet/as_outlet return - a recipe dict, not an instance.
    The node's add() method uses this spec to instantiate the actual DataPort.
    """

    # Port constructor kwargs (id, port_type, default, label, widget, etc.)
    kwargs: Dict[str, Any]

    # Type lineage (recursive for compound types)
    recipe: ElementTypeSpec


def create_port_spec(type_cls: type["IType"], port_type: PortType, id: str, **kwargs) -> PortSpec:
    """
    Create a port specification dict.

    Args:
        type_cls: The IType class (FLOAT, ArrayType[STRING], etc.)
        port_type: port type
        id: Port identifier
        **kwargs: Port configuration (label, default, widget, etc.)

    Returns:
        PortSpec ready for node.add()

    """

    # Normalize default if provided
    if "default" in kwargs:
        kwargs["default"] = normalize_and_validate_default(
            kwargs["default"], type_cls, context=f"as_{port_type.value} for port '{id}'"
        )

    # Build spec: identity as defaults, kwargs override
    # The spec becomes the self-contained truth
    merged_kwargs = {
        **asdict(type_cls.class_identity),  # Identity defaults
        "id": id,
        "port_type": port_type,
        **kwargs,  # User overrides
    }

    return PortSpec(kwargs=merged_kwargs, recipe=serialize_element_type(type_cls))


def serialize_element_type(type_cls: type["IType"]) -> ElementTypeSpec:
    """
    Recursively serialize element type for compound types.

    Args:
        type_cls: Element type class to serialize

    Returns:
        ElementTypeSpec

    Examples:
        serialize_element_type(STRING)
        # → {'registry_key': 'core:type:string'}

        serialize_element_type(ArrayType[STRING])
        # → {
        #     'registry_key': 'core:type:array',
        #     'element_type': {'registry_key': 'core:type:string'}
        #   }
    """
    from haywire.core.types.base import CompoundType

    if not hasattr(type_cls, "class_identity"):
        raise ValueError(f"Type {type_cls.__name__} has no class_identity. Was it decorated with @type?")

    registry_key = type_cls.class_identity.registry_key
    if not registry_key:
        raise ValueError(f"Type {type_cls.__name__} has no registry_key")

    result: ElementTypeSpec = {"registry_key": registry_key}

    # Recurse for nested compound types
    if (
        issubclass(type_cls, CompoundType)
        and hasattr(type_cls, "element_type_cls")
        and type_cls.element_type_cls
    ):
        result["element_type"] = serialize_element_type(type_cls.element_type_cls)

    return result


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
    default_value: Any, cls: type[IType], context: str = "type decorator"
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
        normalized = {"value": default_value}

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
