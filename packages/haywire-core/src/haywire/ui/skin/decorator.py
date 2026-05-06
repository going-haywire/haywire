from typing import Any, Callable, Type, TypeVar

from haywire.core.library.utils import derive_library_identity, reg_key

from .base import BaseSkin, SkinIdentity

# ============================================================================
#    Decorator
# ============================================================================

T = TypeVar("T")


def skin(**kwargs: Any) -> Callable[[Type[T]], Type[T]]:
    """
    Decorator to register a class as a node skin.

    Always invoked with parentheses — `@skin(...)` or `@skin()`. The bare
    `@skin` form (no parens) is not supported.

    Accepts any SkinIdentity field as a keyword argument. Common arguments include:

    Args:
        label (str, optional): Human-readable display name for the skin.
            Defaults to class name if not provided.
        description (str, optional): Human-readable description of the skin.
            Defaults to empty string.
        is_default (bool, optional): Whether this skin should be the default fallback.
            Defaults to False.
        is_error (bool, optional): Whether this skin should handle error cases.
            Defaults to False.
        deprecation_warning (str, optional): Deprecation warning message for the skin.
            Defaults to empty string.
        registry_id (str, optional): Unique identifier for the skin within its library.
            Defaults to class name if not provided.

    Any other keyword arguments will be passed through to the SkinIdentity constructor.
    See the SkinIdentity dataclass for the complete list of available fields.

    Usage:
        # Minimal usage - uses class name for registry_id
        @skin()
        class MySkin(BaseSkin): ...

        # Common customization
        @skin(description="Custom node skin")
        class MySkin(BaseSkin): ...

        # Full customization
        @skin(
            description="Custom node skin for special cases",
            is_default=False
        )
        class CustomSkin(BaseSkin): ...

        # Default skin
        @skin(is_default=True, description="Default node skin")
        class DefaultSkin(BaseSkin): ...

        # Error skin
        @skin(is_error=True, description="Error node skin")
        class ErrorSkin(BaseSkin): ...
    """

    def decorator(inner_cls: Type[T]) -> Type[T]:
        if not issubclass(inner_cls, BaseSkin):
            raise TypeError(f"@skin can only be applied to BaseSkin subclasses, got {inner_cls}")

        # Set defaults from class name if not provided
        kwargs.setdefault("registry_id", inner_cls.__name__)
        kwargs.setdefault("label", inner_cls.__name__)

        # Get library identity (survives hot-reload)
        library_identity = derive_library_identity(inner_cls)

        # Auto-derive registry_key
        kwargs["registry_key"] = reg_key(library_identity.id, "skin", kwargs["registry_id"])

        # Set source info from the class itself
        kwargs["class_name"] = inner_cls.__name__
        kwargs["module"] = inner_cls.__module__

        # Create and attach identity and library
        inner_cls.class_identity = SkinIdentity(**kwargs)
        inner_cls.class_library = library_identity
        return inner_cls

    return decorator
