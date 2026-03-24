from typing import Callable, Type, TypeVar, Union

from haywire.core.types.interface import IType
from haywire.core.library.utils import derive_library_identity, reg_key

from .interface import IWidget
from .identity import WidgetIdentity


# ============================================================================
#    Decorator
# ============================================================================

T = TypeVar("T")


def widget(cls: Type[T] = None, /, **kwargs) -> Union[Type[T], Callable[[Type[T]], Type[T]]]:
    """
    Decorator to register a class as a UI widget.

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
        # Minimal usage - uses class name for registry_id
        @widget
        class MyWidget(BaseWidget): ...

        # Common customization
        @widget(description="Custom widget for text input")
        class MyWidget(BaseWidget): ...

        # Full customization
        @widget(
            registry_id="text_input_widget",
            description="Advanced text input widget with validation",
            _is_error=False
        )
        class TextWidget(BaseWidget): ...

        # Default widget for specific data types
        @widget(description="Number input widget")
        class NumberWidget(BaseWidget): ...

        # Error widget
        @widget(description="Error display widget", _is_error=True)
        class ErrorWidget(BaseWidget): ...
    """

    def decorator(inner_cls: Type[T]) -> Type[T]:
        if not issubclass(inner_cls, IWidget):
            raise TypeError(f"@widget can only be applied to BaseWidget subclasses, got {inner_cls}")

        if "compatible_types" not in kwargs:
            raise ValueError("'compatible_types' must be provided when registering a widget")

        if not isinstance(kwargs["compatible_types"], (set, list)):
            raise TypeError("'compatible_types' must be a set or list of type classes")

        types = kwargs["compatible_types"]

        # However, we allow no type constraints.
        # This has to be explicit by setting an empty set/list.

        for typ in types:
            if not issubclass(typ, IType):
                raise TypeError(f"All 'compatible_types' must be subclasses of IType, got '{typ}'")

        # Set defaults from class name if not provided
        kwargs.setdefault("registry_id", inner_cls.__name__)
        kwargs.setdefault("label", inner_cls.__name__)

        # Get library identity (survives hot-reload)
        library_identity = derive_library_identity(inner_cls)

        # Auto-derive registry_key
        library_id = library_identity.id if library_identity else None
        kwargs["registry_key"] = reg_key(library_id, "widget", kwargs["registry_id"])

        # Create and attach identity and library
        inner_cls.class_identity = WidgetIdentity(**kwargs)
        inner_cls.class_library = library_identity
        return inner_cls

    return decorator if cls is None else decorator(cls)
