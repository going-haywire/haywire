
import inspect
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Type, Optional, TypeVar, Union
from dataclasses import dataclass, field

from ..data.fields import DataField
from ..node.elements import ConfigurableElement

@dataclass
class WidgetIdentity:
    """Core identifying attributes of a widget"""
    registry_id: str = ''  # Set by user for unique ID within library - fallback to class name
    description: str = ''
    default_for: list[str] = field(default_factory=list)  # List of data types this widget should be the default for
    is_error_widget: bool = False

# For widgets
def is_widget(cls):
    try:
        return (inspect.isclass(cls) and
                issubclass(cls, BaseWidget) and
                cls != BaseWidget)
    except TypeError:
        return False

# ============================================================================
#    Decorator
# ============================================================================

T = TypeVar('T')

def widget(cls: Type[T] = None, /, **kwargs) -> Union[Type[T], Callable[[Type[T]], Type[T]]]:
    """
    Decorator to register a class as a UI widget.
    
    Accepts any WidgetIdentity field as a keyword argument. Common arguments include:
    
    Args:
        registry_id (str, optional): Unique identifier for the widget within its library.
            Defaults to class name if not provided.
        description (str, optional): Human-readable description of the widget.
            Defaults to empty string.
        default_for (list[str], optional): List of data types this widget should be the default for.
            Defaults to empty list.
        is_error_widget (bool, optional): Whether this widget should handle error cases.
            Defaults to False.
    
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
            default_for=["STRING", "BYTES"],
            is_error_widget=False
        )
        class TextWidget(BaseWidget): ...

        # Default widget for specific data types
        @widget(default_for=["INT", "FLOAT"], description="Number input widget")
        class NumberWidget(BaseWidget): ...

        # Error widget
        @widget(is_error_widget=True, description="Error display widget")
        class ErrorWidget(BaseWidget): ...
    """
    def decorator(inner_cls: Type[T]) -> Type[T]:
        if not issubclass(inner_cls, BaseWidget):
            raise TypeError(f"@widget can only be applied to BaseWidget subclasses, got {inner_cls}")

        # Set defaults from class name if not provided
        kwargs.setdefault('registry_id', inner_cls.__name__)
        
        inner_cls.class_identity = WidgetIdentity(**kwargs)
        return inner_cls

    return decorator if cls is None else decorator(cls)

# ============================================================================
#    BASE WIDGET CLASS
# ============================================================================

class BaseWidget(ABC):
    """Abstract base class for all widgets"""

    def __init__(self, element: ConfigurableElement):
        self.element: ConfigurableElement = element
        self.element_id: str = element.id
        self.data_field: DataField = element.data
        self.ui_properties: Dict[str, Any] = element.ui.get('properties', {}) if hasattr(element, 'ui') else {}
        self.ui_element = None

        # Add change handler for the data field
        self.data_field.on_changed += self._call_on_model_changed

    def _call_on_model_changed(self, new_value: Any):
        """Handle data field changes by updating the UI"""
        if self.ui_element is not None and new_value is not None:
            self.on_model_change(new_value)

    @abstractmethod
    def on_model_change(self, value: Any):
        """Update the UI element with a new value"""
        pass

    @abstractmethod
    def create_element(self) -> Any:
        """Create and return the NiceGUI element"""
        pass

    def update_value(self, new_value: Any):
        """Update the data field value"""
        self.data_field.set_value(new_value)

    def get_value(self) -> Any:
        """Get the current data field value"""
        return self.data_field.get_value()

    def on_ui_change(self, e):
        self.update_value(e.sender.value)

    def render(self) -> Any:
        """Render the widget and return the UI element"""
        if self.ui_element is None:
            self.ui_element = self.create_element()
            self.ui_element.on('update:modelValue', self.on_ui_change)
            self.ui_element.client.on_disconnect(lambda: self.cleanup())
        return self.ui_element

    def cleanup(self):
        """Clean up event handlers"""
        self.data_field.on_changed -= self._call_on_model_changed

