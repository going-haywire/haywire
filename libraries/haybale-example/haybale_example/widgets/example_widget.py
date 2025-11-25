from typing import Any
from nicegui import ui

from haywire.core.types.ports import DataPort

from haywire.ui.widget.base import BaseWidget
from haywire.ui.widget.decorator import widget

from haybale_example.types.specs import Temperature

@widget(
        description="Custom widget for temperature values with Celsius/Fahrenheit display",
        compatible_types=[Temperature]  # Assuming 'temperature' is a defined type in the system
    )
class TemperatureWidget(BaseWidget):
    """Custom widget for temperature values with Celsius/Fahrenheit display"""

    def __init__(self, element: DataPort):
        super().__init__(element)
        self.conversion_label = None
        self.unit = self.ui_properties.get('unit', 'celsius')

    def _celsius_to_fahrenheit(self, celsius: float) -> float:
        """Convert Celsius to Fahrenheit"""
        return (celsius * 9/5) + 32

    def _fahrenheit_to_celsius(self, fahrenheit: float) -> float:
        """Convert Fahrenheit to Celsius"""
        return (fahrenheit - 32) * 5/9

    def _get_display_value(self, celsius_value: float) -> float:
        """Get the display value based on the current unit"""
        return celsius_value if self.unit == 'celsius' else self._celsius_to_fahrenheit(celsius_value)

    def _get_conversion_display(self, celsius_value: float) -> str:
        """Get the conversion display text"""
        if self.unit == 'celsius':
            fahrenheit_value = self._celsius_to_fahrenheit(celsius_value)
            return f"({fahrenheit_value:.1f}°F)"
        else:
            return f"({celsius_value:.1f}°C)"

    def on_value_change(self, value: float):  
        """Update the UI elements when the model value changes"""  
        celsius_value = self._get_typed_value()
        display_value = self._get_display_value(celsius_value)
        
        # Update the main input
        if self.ui_element is not None:
            self.ui_element.value = display_value
        
        # Update the conversion label
        if self.conversion_label is not None:
            self.conversion_label.text = self._get_conversion_display(celsius_value)

    def on_ui_change(self, e):
        """Override to handle unit conversion before updating the model"""
        display_value = e.sender.value
        # Convert display value back to Celsius for storage
        celsius_value = display_value if self.unit == 'celsius' else self._fahrenheit_to_celsius(display_value)
        
        # Update the model with Celsius value
        self._update_typed_value(celsius_value)
        
        # Update the conversion label
        if self.conversion_label is not None:
            self.conversion_label.text = self._get_conversion_display(celsius_value)

    def create_element(self) -> Any:
        """Create a temperature widget with unit conversion"""
        temp_celsius = self._get_typed_value() or 0
        display_value = self._get_display_value(temp_celsius)

        with ui.column().classes('w-full') as wrapper:
            # Number input for the temperature
            number_kwargs = {
                'value': display_value,
                'suffix': '°C' if self.unit == 'celsius' else '°F',
                'step': 0.1,
                'precision': 1
            }

            temp_input = ui.number(**number_kwargs).classes('w-full')

            # Display conversion
            self.conversion_label = ui.label(self._get_conversion_display(temp_celsius)).classes('text-sm text-gray-500')

        return temp_input