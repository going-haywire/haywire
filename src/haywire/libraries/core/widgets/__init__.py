"""
Core widget registration and exports
"""

from haywire.core.inventory.registry.widget import WidgetRegistry
from haywire.core.inventory.folder_scan import folder_scan_for_classes
from haywire.core.inventory.registry.library import LibraryMetadata
from haywire.core.data.enums import DataType
from haywire.core.inventory.utils import camel_to_dot_case
from haywire.core.ui.base import is_widget

# Import all widget classes
from .base import ErrorWidget
from .basic_widgets import (
    TextInputWidget, 
    NumberWidget, 
    CheckboxWidget, 
    SwitchWidget
)
from .display_widgets import (
    LabelWidget
)


def register_widgets(widget_registry: WidgetRegistry, library_metadata: LibraryMetadata):
    """Register all core widgets with the widget registry"""

    widgets = folder_scan_for_classes(
        library_path=__path__[0],
        class_filter=is_widget
    )

    # Register all discovered widgets
    for widget_class in widgets:
        widget_registry.register_widget(widget_class, library_metadata)

    # Register default widgets for scalar data types
    widget_registry.register_default_widget(DataType.STRING, TextInputWidget)
    widget_registry.register_default_widget(DataType.INT, NumberWidget)
    widget_registry.register_default_widget(DataType.FLOAT, NumberWidget)
    widget_registry.register_default_widget(DataType.BOOL, CheckboxWidget)
    widget_registry.register_default_widget(DataType.BYTES, TextInputWidget)  # Display as text
    widget_registry.register_default_widget(DataType.DICT, LabelWidget)  # Read-only for complex types
    widget_registry.register_default_widget(DataType.OBJECT, LabelWidget)  # Read-only for complex types

    # Register error widget
    widget_registry.register_error_widget(ErrorWidget)


__all__ = [
    'ErrorWidget', 
    'TextInputWidget',
    'NumberWidget',
    'CheckboxWidget',
    'SwitchWidget',
    'LabelWidget',
    'register_widgets'
]
