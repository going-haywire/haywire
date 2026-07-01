from typing import Any, Callable, Type, TypeVar

from haywire.core.library.utils import WIDGET, derive_library_identity, reg_key

from .interface import IWidget
from .identity import WidgetIdentity


# ============================================================================
#    Decorator
# ============================================================================

T = TypeVar("T")


def widget(**kwargs: Any) -> Callable[[Type[T]], Type[T]]:
    """
    Decorator to register a class as a UI widget.

    Always invoked with parentheses — `@widget(...)`. The bare `@widget`
    form (no parens) is not supported.

    Accepts any WidgetIdentity field as a keyword argument. Common arguments include:

    Args:
        registry_id (str, optional): Unique identifier for the widget within its library.
            Defaults to class name if not provided.
        label (str, optional): Human-readable display name for the widget.
            Defaults to class name if not provided.
        description (str, optional): Human-readable description of the widget.
            Defaults to empty string.
        deprecation_warning (str, optional): Deprecation warning message for the widget.
            Defaults to empty string.

    Any other keyword arguments will be passed through to the WidgetIdentity constructor.
    See the WidgetIdentity dataclass for the complete list of available fields.

    Usage:
        # Common customization
        @widget(description="Custom widget for text input")
        class MyWidget(BaseWidget): ...

        # Full customization
        @widget(
            description="Advanced text input widget with validation",
            _is_error=False,
        )
        class TextWidget(BaseWidget): ...

        # Error widget
        @widget(description="Error display widget", _is_error=True)
        class ErrorWidget(BaseWidget): ...
    """

    def decorator(inner_cls: Type[T]) -> Type[T]:
        if not issubclass(inner_cls, IWidget):
            raise TypeError(f"@widget can only be applied to BaseWidget subclasses, got {inner_cls}")

        # Set defaults from class name if not provided
        kwargs.setdefault("registry_id", inner_cls.__name__)
        kwargs.setdefault("label", inner_cls.__name__)

        # Get library identity (survives hot-reload)
        library_identity = derive_library_identity(inner_cls)

        # Auto-derive registry_key
        kwargs["registry_key"] = reg_key(library_identity.id, WIDGET, kwargs["registry_id"])

        # Set source info from the class itself
        kwargs["class_name"] = inner_cls.__name__
        kwargs["module"] = inner_cls.__module__

        # Create and attach identity and library
        inner_cls.class_identity = WidgetIdentity(**kwargs)
        inner_cls.class_library = library_identity
        return inner_cls

    return decorator
