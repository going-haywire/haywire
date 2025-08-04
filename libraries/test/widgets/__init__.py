"""
Test widgets for the test library
"""

import sys
import os
from typing import Any, Dict
from nicegui import ui

# Add project paths for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from haywire.libraries.core.widgets.base import BaseWidget
from haywire.libraries.registry import WidgetRegistry
from haywire.core.data.fields import DataField


class TemperatureWidget(BaseWidget):
    """Custom widget for temperature values with Celsius/Fahrenheit display"""
    
    def create_element(self) -> Any:
        """Create a temperature widget with unit conversion"""
        temp_celsius = self.get_value() or 0
        temp_fahrenheit = (temp_celsius * 9/5) + 32
        
        # Get unit preference from props
        unit = self.ui_props.get('unit', 'celsius')
        display_value = temp_celsius if unit == 'celsius' else temp_fahrenheit
        
        with ui.column().classes('w-full'):
            # Number input for the temperature
            number_kwargs = {
                'value': display_value,
                'suffix': '°C' if unit == 'celsius' else '°F',
                'step': 0.1,
                'precision': 1
            }
            
            def update_value(e):
                # Convert back to Celsius if needed
                celsius_value = e.value if unit == 'celsius' else (e.value - 32) * 5/9
                self.update_value(celsius_value)
                # Update the conversion display
                other_value = (celsius_value * 9/5) + 32 if unit == 'celsius' else celsius_value
                other_unit = '°F' if unit == 'celsius' else '°C'
                conversion_label.text = f"({other_value:.1f}{other_unit})"
            
            temp_input = ui.number(**number_kwargs, on_change=update_value).classes('w-full')
            
            # Display conversion
            other_value = temp_fahrenheit if unit == 'celsius' else temp_celsius
            other_unit = '°F' if unit == 'celsius' else '°C'
            conversion_label = ui.label(f"({other_value:.1f}{other_unit})").classes('text-sm text-gray-500')
        
        return temp_input


def register_test_widgets(widget_registry: WidgetRegistry):
    """Register test widgets with the widget registry"""
    widget_registry.register('temperature', TemperatureWidget)


__all__ = [
    'TemperatureWidget',
    'register_test_widgets'
]
