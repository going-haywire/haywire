"""
Core widget registration and exports
"""

from haywire.core.registry.registry import WidgetRegistry
from haywire.core.data.enums import DataType

# Import all widget classes
from .base import ErrorWidget
from .basic_widgets import (
    TextInputWidget, NumberWidget, CheckboxWidget, SwitchWidget,
    SelectWidget, SliderWidget, KnobWidget
)
from .display_widgets import LabelWidget, ProgressWidget, BadgeWidget


def register_widgets(widget_registry: WidgetRegistry):
    """Register all core widgets with the widget registry"""
    
    # Register error widget
    widget_registry.register_error_widget(ErrorWidget)
    
    # Register basic input widgets
    widget_registry.register('text_input', TextInputWidget)
    widget_registry.register('input', TextInputWidget)  # Alias
    widget_registry.register('number', NumberWidget)
    widget_registry.register('checkbox', CheckboxWidget)
    widget_registry.register('switch', SwitchWidget)
    widget_registry.register('select', SelectWidget)
    widget_registry.register('dropdown', SelectWidget)  # Alias
    widget_registry.register('slider', SliderWidget)
    widget_registry.register('knob', KnobWidget)
    
    # Register display widgets
    widget_registry.register('label', LabelWidget)
    widget_registry.register('progress', ProgressWidget)
    widget_registry.register('badge', BadgeWidget)
    
    # Register default widgets for scalar data types
    widget_registry.register_default_widget(DataType.STRING, 'text_input')
    widget_registry.register_default_widget(DataType.INT, 'number')
    widget_registry.register_default_widget(DataType.FLOAT, 'number')
    widget_registry.register_default_widget(DataType.BOOL, 'checkbox')
    widget_registry.register_default_widget(DataType.BYTES, 'text_input')  # Display as text
    widget_registry.register_default_widget(DataType.DICT, 'label')  # Read-only for complex types
    widget_registry.register_default_widget(DataType.OBJECT, 'label')  # Read-only for complex types


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
