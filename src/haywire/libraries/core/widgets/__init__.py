"""
Core widget registration and exports
"""

from haywire.core.registry.auto_discover import auto_discover_classes, is_widget
from haywire.core.registry.registry import WidgetRegistry, LibraryMetadata
from haywire.core.data.enums import DataType
from haywire.core.registry.utils import camel_to_dot_case

# Import all widget classes
from .base import ErrorWidget
from .basic_widgets import (
    TextInputWidget, NumberWidget, CheckboxWidget, SwitchWidget,
    SelectWidget, SliderWidget, KnobWidget
)
from .display_widgets import LabelWidget, ProgressWidget, BadgeWidget


def register_widgets(widget_registry: WidgetRegistry, library_metadata: LibraryMetadata):
    """Register all core widgets with the widget registry"""

    widgets = auto_discover_classes(
        library_path=__path__[0],
        class_filter=is_widget
    )

    # Register all discovered widgets
    for widget_class in widgets:
        print(f"Test-Registering widget: '{widget_class.__name__}' as :'{camel_to_dot_case(widget_class.__name__)}'")
        #widget_registry.register_widget(widget_class, library_metadata)

    
    # Register basic input widgets
    widget_registry.register_widget(TextInputWidget, library_metadata)
    widget_registry.register_widget(NumberWidget, library_metadata)
    widget_registry.register_widget(CheckboxWidget, library_metadata)
    widget_registry.register_widget(SwitchWidget, library_metadata)
    widget_registry.register_widget(SelectWidget, library_metadata)
    widget_registry.register_widget(SliderWidget, library_metadata)
    widget_registry.register_widget(KnobWidget, library_metadata)

    # Register display widgets
    widget_registry.register_widget(LabelWidget, library_metadata)
    widget_registry.register_widget(ProgressWidget, library_metadata)
    widget_registry.register_widget(BadgeWidget, library_metadata)

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
    'SelectWidget',
    'SliderWidget',
    'KnobWidget',
    'LabelWidget',
    'ProgressWidget',
    'BadgeWidget',
    'register_widgets'
]
