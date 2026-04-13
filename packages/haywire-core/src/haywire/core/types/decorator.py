"""
Type Decorators - Decorators for defining Haywire data types.

This module provides decorators for creating Haywire data types:
- @primitive_type: For primitive type wrappers (FLOAT, INT, etc.) and their variants (Temperature)
- @compound_type: For custom data structures with serialization (MeshData, TestData)
- @type_: Legacy decorator (deprecated, use @primitive_type or @compound_type instead)
"""

from typing import Optional, Type, TypeVar, Callable
from dataclasses import asdict


from ..library.utils import derive_library_identity, reg_key
from .base import BaseType
from .identity import DataTypeIdentity
from .interface import IType
from .base import PrimitiveType
from .utils import normalize_and_validate_default

T = TypeVar("T")


def type(**kwargs) -> Callable[[Type[T]], Type[T]]:
    """
    Decorator for all Haywire data types (both primitive and complex).

    Use this for:
    - Base primitive types that wrap Python built-ins (FLOAT wraps float, INT wraps int)
    - Derived type variants that inherit from primitives (Temperature extends FLOAT)
    - Complex types with multiple fields (MeshData, Color, etc.)

    Examples:
        # Primitive type:
        @type(
            color='#50b0ff',
            default={'value': 0.0}
        )
        @dataclass
        class FLOAT(PrimitiveType[float]):
            pass

        # Derived variant - can override parent defaults:
        @type(
            default={'value': 20.0},  # Override default
            ui={'properties': {'unit': '°C'}}
        )
        class Temperature(FLOAT):
            pass

        # Complex type:
        @type(
            label='3D Mesh',
            color='#4CAF50',
            default={'vertices': [], 'faces': [], 'name': 'Default Mesh'}
        )
        @dataclass
        class MeshData(BaseType):
            vertices: List[Tuple[float, float, float]] = field(default_factory=list)
            faces: List[Tuple[int, int, int]] = field(default_factory=list)
            name: str = "Unnamed Mesh"

    Args:
        cls (type, optional): The Python type being wrapped (auto-set to the decorated class).
        label (str, optional): Human-readable display name.
        description (str, optional): Type description.
        color (str, optional): UI pin color (hex).
        icon (str, optional): UI pin icon.
        icon_in (str, optional): Icon for inlet pins.
        icon_in_multi (str, optional): Icon for multi-link inlet pins.
        icon_out (str, optional): Icon for outlet pins.
        icon_out_multi (str, optional): Icon for multi-link outlet pins.
        widget_key (str, optional): Widget for editing values. NOT RECOMENDED TO USE
        widget_config (dict, optional): Additional widget configuration properties. NOT RECOMENDED TO USE
        flow_type (FlowType, optional): DATA, CTRL, or NONE.
        default (dict, required): Dict of constructor kwargs for default instance.
        help_url (str, optional): Documentation URL.
        deprecation_warning (str, optional): Deprecation warning message.
        store_strategy: (StoreStrategy, optional): When to serialize field values (default: NEVER).
        registry_id (str, optional): Unique identifier within library. Defaults to class name.

    Returns:
        Decorated class with class_identity attribute

    Raises:
        TypeError: If 'default' is missing or not a dict
        TypeError: If class doesn't inherit from IType
    """

    def decorator(inner_cls: Type[T]) -> Type[T]:
        # Ensure inherits from IType
        if not issubclass(inner_cls, IType):
            raise TypeError(
                f"@type decorator requires {inner_cls.__name__} to inherit from IType "
                f"(via BaseType or PrimitiveType)"
            )

        # Initialize _parameterized_cache for CompoundType if needed
        if hasattr(inner_cls, "_parameterized_cache"):
            inner_cls._parameterized_cache = {}

        # Get library identity and attach (survives hot-reload)
        library_identity = derive_library_identity(inner_cls)
        inner_cls.class_library = library_identity

        # Set cls to the decorated class itself
        kwargs["type_cls"] = inner_cls

        # Check if this inherits from another Type (derived variant)
        parent_identity: Optional[DataTypeIdentity] = None
        for base in inner_cls.__bases__:
            # Skip abstract base classes
            if base in (BaseType, PrimitiveType, IType):
                continue
            # Check if this base is a registered type
            if issubclass(base, IType) and hasattr(base, "class_identity"):
                parent_identity = base.class_identity
                break

        # Build identity dict
        if parent_identity:
            # Start with parent's identity
            identity_dict = asdict(parent_identity)
            # Derived types must have their own registry_id —
            # inheriting the parent's would cause a registry key collision.
            # Use the child class name unless explicitly overridden.
            if "registry_id" not in kwargs:
                identity_dict["registry_id"] = inner_cls.__name__
            # Override with explicitly provided kwargs
            identity_dict.update(kwargs)
        else:
            # No parent, use defaults
            kwargs.setdefault("registry_id", inner_cls.__name__)
            kwargs.setdefault("label", inner_cls.__name__)
            kwargs.setdefault("description", inner_cls.__doc__.strip() if inner_cls.__doc__ else "")
            identity_dict = kwargs

        # Validate 'default' parameter
        if "default" not in identity_dict:
            raise TypeError(
                f"@type decorator for {inner_cls.__name__} missing required 'default' parameter. "
                f"The 'default' should be a dict of constructor kwargs for serialization.\n"
                f"Examples:\n"
                f"  - Primitives: default={{'value': 0.0}}\n"
                f"  - Complex types: default={{'field1': val1, 'field2': val2}}\n"
                f"  - Types with custom create_default(): default={{'value': None}}"
            )

        # Normalize and validate default
        identity_dict["default"] = normalize_and_validate_default(
            identity_dict["default"], inner_cls, context="@type decorator"
        )

        # Set registry_key (always regenerate for this class)
        library_id = library_identity.id if library_identity else None
        identity_dict["registry_key"] = reg_key(library_id, "type", identity_dict["registry_id"])

        # Set source info from the class itself
        identity_dict["class_name"] = inner_cls.__name__
        identity_dict["module"] = inner_cls.__module__

        # Create and attach identity
        inner_cls.class_identity = DataTypeIdentity(**identity_dict)

        return inner_cls

    return decorator
