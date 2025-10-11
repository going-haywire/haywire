import logging
from typing import Type, TypeVar, Optional, Callable, Union

from haywire.core.data.enums import DataContainerType, DataType
from haywire.core.data.fields import DataField
from ..base import LibraryMetadata
from haywire.core.ui.base import BaseWidget, is_widget

from ..base import BaseClassRegistry, FileChangeEvent, FileEventType, RegistryFolder
from ..utils import camel_to_dot_case, reg_key

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


class WidgetRegistry(BaseClassRegistry):
    """Registry for UI widgets that can render data fields"""
    directory_name: str = RegistryFolder.WIDGETS.value
    class_filter = lambda self, cls: is_widget(cls)  # Use the widget filter

    def __init__(self):
        super().__init__()
        self._default_widgets: dict[DataType, type] = {}
        self._error_widget: type | None = None

    def register_widget(self, widget: type[BaseWidget], metadata: LibraryMetadata):
        """Register a UI widget with its metadata"""

        registry_key = reg_key(metadata.id, widget.class_identity['registry_id'])

        self._register(registry_key, widget, metadata=metadata)

    def unregister_widget(self, widget_name: str) -> type[BaseWidget] | None:
        """Unregister a UI widget by its haywire name
        Args:
            widget_name: The haywire name of the widget to unregister
        """
        # Remove from default widgets if it was set
        for data_type, default_widget in list(self._default_widgets.items()):
            if default_widget == widget_name:
                del self._default_widgets[data_type]
                logging.warning(f"Widget '{widget_name}' removed from default widgets for '{data_type}'")
        
        removed_class = super()._unregister(widget_name)

        if removed_class == self._error_widget:
            self._error_widget = None
            logging.warning(f"Error widget '{widget_name}' unregistered, no error widget left in registry")

        return removed_class

    def register_default_widget(self, data_type: DataType, widget_class: type[BaseWidget]):
        """Register a default widget for a data type"""

        # get the widget name from the class
        # This assures to work even it the widget class was removed from the registry
        widget_name = next((name for name, cls in self._items.items() if cls == widget_class), None)

        if widget_name:
            self._default_widgets[data_type] = widget_name
        else:
            logging.warning(f"Widget class '{widget_class.__name__}' not found in registry, cannot register default widget for '{data_type}'")

    def register_error_widget(self, widget_class: type[BaseWidget]):
        """Register the error widget class"""
        self._error_widget = widget_class

    def handle_module_change(self, module: str, event: FileChangeEvent, metadata: LibraryMetadata):
        """
        Handle file change events for node modules.

        Args:
            event: FileChangeEvent containing file path and event type
        """
        if event.event_type == FileEventType.CREATED:
            added_classes = self._on_creation(module)
            if added_classes:
                for cls_name in added_classes:
                    self.register_widget(cls_name, metadata)
        elif event.event_type == FileEventType.MODIFIED:
            added_classes, removed_classes = self._on_change(module)
            if removed_classes:
                for cls_name in removed_classes:
                    self.unregister_widget(cls_name)
            if added_classes:
                for cls_name in added_classes:
                    self.register_widget(cls_name, metadata)
        elif event.event_type == FileEventType.DELETED:
            removed_classes = self._on_delete(module)
            if removed_classes:
                for cls_name in removed_classes:
                    self.unregister_widget(cls_name)


    def get_widget_class(self, widget_name: str | None, data_field: DataField) -> type[BaseWidget]:
        """
        Get widget class with fallback strategy:
        1. Try exact widget name lookup
        2. Fallback to default for scalar types
        3. Return error widget
        """
        # 1. Try exact widget name lookup
        if widget_name and self.has(widget_name):
            return self.get(widget_name)

        # 2. Fallback to default for scalar types
        default_widget_name = self._default_widgets.get(data_field.type)
        if default_widget_name and self.has(default_widget_name):
            return self.get(default_widget_name)

        # 3. Return error widget
        if self._error_widget:
            return self._error_widget

        # Fallback if no error widget registered
        raise RuntimeError(f"No widget found for '{widget_name}' and no error widget registered")