"""
Core widget registration and exports
"""

from haywire.core.inventory.library import BaseLibrary
from haywire.core.inventory.registry.widget_reg import WidgetRegistry
from haywire.core.inventory.folder_scan_for_classes import folder_scan_for_classes
from haywire.core.data.enums import DataType
from haywire.core.inventory.utils import camel_to_dot_case
from haywire.core.ui.base_widget import is_widget

# Import all widget classes
from .error_widget import ErrorWidget
from .basic_widgets import (
    TextInputWidget, 
    NumberWidget, 
    CheckboxWidget, 
    SwitchWidget
)
from .display_widgets import (
    LabelWidget
)


def register_widgets(library: BaseLibrary):
    """Register all core widgets with the widget registry"""

    widgets = folder_scan_for_classes(
        library_path=__path__[0],
        library=library,
        class_filter=is_widget
    )

    reg: WidgetRegistry = library.get_registry(WidgetRegistry)
    if reg:
        # Register all discovered widgets
        for widget_class in widgets:
            reg.register_widget(widget_class, library.identity)

        # Register default widgets for scalar data types
        reg.register_default_widget(DataType.STRING, TextInputWidget)
        reg.register_default_widget(DataType.INT, NumberWidget)
        reg.register_default_widget(DataType.FLOAT, NumberWidget)
        reg.register_default_widget(DataType.BOOL, CheckboxWidget)
        reg.register_default_widget(DataType.BYTES, TextInputWidget)  # Display as text
        reg.register_default_widget(DataType.DICT, LabelWidget)  # Read-only for complex types
        reg.register_default_widget(DataType.OBJECT, LabelWidget)  # Read-only for complex types

        # Register error widget
        reg.register_error_widget(ErrorWidget)


__all__ = [
    'ErrorWidget', 
    'TextInputWidget',
    'NumberWidget',
    'CheckboxWidget',
    'SwitchWidget',
    'LabelWidget',
    'register_widgets'
]
