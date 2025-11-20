
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Type, Optional, TypeVar, Union
from dataclasses import dataclass, field

from haywire.core.errors.haywire_error import HaywireError

from ..data.fields import DataField
from ..types.ports import DataPort
from ..library.base_identity import BaseIdentity
from ..library.utils import derive_library_identity, reg_key

@dataclass
class WidgetIdentity(BaseIdentity):
    """Core identifying attributes of a widget"""
    _is_error: bool = False
    _error_priority: int = 0

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
        label (str, optional): Human-readable display name for the widget.
            Defaults to class name if not provided.
        description (str, optional): Human-readable description of the widget.
            Defaults to empty string.
        _is_error (bool, optional): Whether this widget should handle error cases.
            Defaults to False.
        _error_priority (int, optional): Priority for error widgets when multiple are registered.
            Higher values take precedence. Defaults to 0.
    
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
        if not issubclass(inner_cls, BaseWidget):
            raise TypeError(f"@widget can only be applied to BaseWidget subclasses, got {inner_cls}")

        # Set defaults from class name if not provided
        kwargs.setdefault('registry_id', inner_cls.__name__)
        kwargs.setdefault('label', inner_cls.__name__)
        
        # Get library identity (survives hot-reload)
        library_identity = derive_library_identity(inner_cls)
        
        # Auto-derive registry_key
        library_id = library_identity.id if library_identity else None
        kwargs['registry_key'] = reg_key(library_id, 'widget', kwargs['registry_id'])
        
        # Create and attach identity and library
        inner_cls.class_identity = WidgetIdentity(**kwargs)
        inner_cls.class_library = library_identity
        return inner_cls

    return decorator if cls is None else decorator(cls)

# ============================================================================
#    BASE WIDGET CLASS
# ============================================================================

class BaseWidget(ABC):
    """Abstract base class for all widgets
    
    Args:
        element (DataPort): The data port this widget is associated with.
        error (Optional[HaywireError]): Optional error information.
    """

    def __init__(self, element: DataPort, error: Optional[HaywireError] = None):
        self.element: DataPort = element
        self.element_id: str = element.id
        self.data_field: DataField = element.data
        self.ui_properties: Dict[str, Any] = element.ui.get('properties', {}) if hasattr(element, 'ui') else {}
        self.ui_element = None
        self.error: Optional[HaywireError] = error

        # Add change handler for the data field
        self.data_field.on_changed += self._call_on_model_changed

    def _call_on_model_changed(self, new_value: Any):
        """Handle data field changes by updating the UI"""
        if self.ui_element is not None and new_value is not None:
            self.on_value_change(new_value)

    @abstractmethod
    def on_value_change(self, value: Any):
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
        print(f"Cleaning up widget: {self.class_identity.registry_key} for element ID: {self.element_id}")
        self.element = None
        self.element_id = None

        """Clean up event handlers"""
        self.data_field.on_changed -= self._call_on_model_changed

        self.data_field = None

