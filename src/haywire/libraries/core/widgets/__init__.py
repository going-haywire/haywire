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
    widget_registry.register('core.text_input', TextInputWidget)
    widget_registry.register('core.input', TextInputWidget)  # Alias
    widget_registry.register('core.number', NumberWidget)
    widget_registry.register('core.checkbox', CheckboxWidget)
    widget_registry.register('core.switch', SwitchWidget)
    widget_registry.register('core.select', SelectWidget)
    widget_registry.register('core.dropdown', SelectWidget)  # Alias
    widget_registry.register('core.slider', SliderWidget)
    widget_registry.register('core.knob', KnobWidget)
    
    # Register display widgets
    widget_registry.register('core.label', LabelWidget)
    widget_registry.register('core.progress', ProgressWidget)
    widget_registry.register('core.badge', BadgeWidget)
    
    # Register default widgets for scalar data types
    widget_registry.register_default_widget(DataType.STRING, 'core.text_input')
    widget_registry.register_default_widget(DataType.INT, 'core.number')
    widget_registry.register_default_widget(DataType.FLOAT, 'core.number')
    widget_registry.register_default_widget(DataType.BOOL, 'core.checkbox')
    widget_registry.register_default_widget(DataType.BYTES, 'core.text_input')  # Display as text
    widget_registry.register_default_widget(DataType.DICT, 'core.label')  # Read-only for complex types
    widget_registry.register_default_widget(DataType.OBJECT, 'core.label')  # Read-only for complex types


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
