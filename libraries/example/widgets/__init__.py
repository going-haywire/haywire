"""
Test widgets for the test library
"""

from typing import Any, Dict
from nicegui import ui

from haywire.ui.base import BaseWidget
from haywire.core.registry.base import LibraryMetadata
from haywire.core.registry.registry import WidgetRegistry

class TemperatureWidget(BaseWidget):
    """Custom widget for temperature values with Celsius/Fahrenheit display"""
    
    def create_element(self) -> Any:
        """Create a temperature widget with unit conversion"""
        temp_celsius = self.get_value() or 0
        temp_fahrenheit = (temp_celsius * 9/5) + 32
        
        # Get unit preference from props
        unit = self.ui_properties.get('unit', 'celsius')
        display_value = temp_celsius if unit == 'celsius' else temp_fahrenheit
        
        with ui.column().classes('w-full') as wrapper:
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
        
        return wrapper


def register_widgets(widget_registry: WidgetRegistry, library_metadata: LibraryMetadata):
    """Register test widgets with the widget registry"""
    widget_registry.register('example.temperature', TemperatureWidget)

__all__ = [
    'TemperatureWidget',
    'register_widgets'
]
