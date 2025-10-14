import logging
from typing import TypeVar, Optional, Union
import logging

from haywire.core.data.enums import DataContainerType, DataType
from haywire.core.data.fields import DataField
from haywire.core.ui.base_widget import BaseWidget
from ..library_identity import LibraryIdentity
from haywire.core.ui.base_widget import is_widget

from ..base import BaseClassRegistry, FileChangeEvent, FileEventType, RegistryFolder
from ..utils import camel_to_dot_case, reg_key

class WidgetRegistry(BaseClassRegistry):
    """Registry for UI widgets that can render data fields"""
    directory_name: str = RegistryFolder.WIDGETS.value
    class_filter = lambda self, cls: is_widget(cls)  # Use the widget filter

    def __init__(self):
        super().__init__()
        self._default_widgets: dict[DataType, type] = {}
        self._error_widget: type | None = None

    def _register(self, widget: type[BaseWidget], library_identity: LibraryIdentity):
        """Register a UI widget with its metadata"""

        widget.class_library = library_identity
        registry_key = reg_key(library_identity.id, widget.class_identity.registry_id)

        # Check if this widget has default_for data types and register them automatically
        if hasattr(widget, 'class_identity') and widget.class_identity.default_for:
            for data_type_str in widget.class_identity.default_for:
                try:
                    data_type = DataType(data_type_str)
                    self._default_widgets[data_type] = widget
                except ValueError:
                    logging.warning(f"Invalid data type '{data_type_str}' in widget '{widget.__name__}' default_for list")

        # Check if this is an error widget and register it automatically
        if hasattr(widget, 'class_identity') and widget.class_identity.is_error_widget:
            self._error_widget = widget
        else:
            # we only register non-error widgets in the main registry
            super()._register(registry_key, widget)


    def _unregister(self, widget_name: str) -> type[BaseWidget] | None:
        """Unregister a UI widget by its haywire name
        Args:
            widget_name: The haywire name of the widget to unregister
        """
        # Remove from default widgets if it was set  
        removed_class = self.get(widget_name)
        for data_type, default_widget_class in list(self._default_widgets.items()):
            if default_widget_class == removed_class:
                del self._default_widgets[data_type]
                logging.warning(f"Widget '{widget_name}' removed from default widgets for '{data_type}'")
        
        removed_class = super()._unregister(widget_name)

        if removed_class == self._error_widget:
            self._error_widget = None
            logging.warning(f"Error widget '{widget_name}' unregistered, no error widget left in registry")

        return removed_class

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
        default_widget_class = self._default_widgets.get(data_field.type)
        if default_widget_class:
            return default_widget_class

        # 3. Return error widget
        if self._error_widget:
            return self._error_widget

        # Fallback if no error widget registered
        raise RuntimeError(f"No widget found for '{widget_name}' and no error widget registered")