from haywire.core.data.enums import DataCategory, DataType
from haywire.core.data.fields import DataField
from haywire.core.registry.base import BaseClassRegistry, LibraryMetadata, RegistryFolder
from haywire.core.registry.utils import camel_to_dot_case
from haywire.core.ui.base import BaseWidget


import logging


class WidgetRegistry(BaseClassRegistry):
    """Registry for UI widgets that can render data fields"""
    directory_name: str = RegistryFolder.WIDGETS.value

    def __init__(self):
        super().__init__()
        self._default_widgets: dict[DataType, type] = {}
        self._error_widget: type | None = None

    def register_widget(self, widget: type[BaseWidget], metadata: LibraryMetadata):
        """Register a UI widget with its metadata"""

        widget_name = camel_to_dot_case(widget.__name__)

        keyname = f"{metadata.name}:{widget_name}"

        self._register(keyname, widget, metadata=metadata)

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
        if data_field.category == DataCategory.SCALAR:
            default_widget_name = self._default_widgets.get(data_field.type)
            if default_widget_name and self.has(default_widget_name):
                return self.get(default_widget_name)

        # 3. Return error widget
        if self._error_widget:
            return self._error_widget

        # Fallback if no error widget registered
        raise RuntimeError(f"No widget found for '{widget_name}' and no error widget registered")