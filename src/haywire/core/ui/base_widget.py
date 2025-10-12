
import inspect
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Type, Optional, TypeVar, Union

from ..data.fields import DataField
from ..node.elements import ConfigurableElement

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

def widget(cls: Type[T] = None, /, *,
           description: str,
           registry_id: Optional[str] = None,
           default_for: Optional[list[str]] = None,
           is_error_widget: bool = False) -> Union[Type[T], Callable[[Type[T]], Type[T]]]:
    """
    Decorator to register a class as a UI widget.

    Args:
        registry_id: Unique identifier for the widget
        description: Human-readable description
        default_for: List of data types this widget should be the default for
        is_error_widget: Whether this widget should handle error cases

    Usage:
        @widget
        class MyWidget(BaseWidget): ...

        @widget(registry_id="custom_id", description="Custom widget")
        class MyWidget(BaseWidget): ...

        @widget(default_for=["STRING", "BYTES"], description="Text widget")
        class TextWidget(BaseWidget): ...

        @widget(is_error_widget=True)
        class ErrorWidget(BaseWidget): ...
    """
    def decorator(inner_cls: Type[T]) -> Type[T]:
        if not issubclass(inner_cls, BaseWidget):
            raise TypeError(f"@widget can only be applied to BaseWidget subclasses, got {inner_cls}")

        # Store widget metadata
        inner_cls.class_identity = {
            'description': description or '',
            'registry_id': registry_id or inner_cls.__name__,
            'default_for': default_for or [],
            'is_error_widget': is_error_widget
        }

        return inner_cls

    if cls is None:
        return decorator
    return decorator(cls)

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

