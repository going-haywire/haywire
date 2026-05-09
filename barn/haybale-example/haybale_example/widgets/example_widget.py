from typing import Any
from nicegui import ui


from haybale_core.types import FLOAT, INT
from haywire.ui.widget.base import BaseWidget
from haywire.ui.widget.binding import PropertyBinding
from haywire.ui.widget.converters import BindingConverter, BindingMode, Converters
from haywire.ui.widget.decorator import widget

from haybale_example.types.specs import Temperature


@widget(description="Number widget with validation", compatible_types=[FLOAT, INT])
class ValidatedNumberWidget(BaseWidget):
    """Number widget with range validation and custom formatting"""

    def configure_bindings(self) -> None:
        props = self._config.get("properties", {})
        min_val = props.get("min")
        max_val = props.get("max")

        if min_val is not None or max_val is not None:
            # Use range validation
            self.add_binding(
                self.create_default_binding(
                    converter=Converters.chain(
                        Converters.primitive(default_value=0),
                        Converters.range(min_value=min_val, max_value=max_val, clamp=True),
                    )
                )
            )
        else:
            # Simple binding
            self.add_binding(self.create_default_binding())

    def create_element(self) -> Any:
        props = self._config.get("properties", {})
        kwargs = {"value": 0}

        for prop in ["label", "min", "max", "step", "precision", "prefix", "suffix"]:
            if prop in props:
                kwargs[prop] = props[prop]

        return ui.number(**kwargs).classes("w-full")


@widget(description="Temperature with unit conversion", compatible_types=[Temperature])
class TemperatureWidget(BaseWidget):
    """
    Temperature widget demonstrating:
    - Custom converter for unit conversion
    - Multiple UI elements with separate bindings
    - Read-only conversion display
    """

    def __init__(self, element):
        super().__init__(element)
        self.unit = self._config.get("properties", {}).get("unit", "celsius")
        self.conversion_label = None

    def configure_bindings(self) -> None:
        # Main input with unit conversion
        self.add_binding(
            PropertyBinding(
                source_property="value",
                converter=UnitConversionConverter(self.unit),
                mode=BindingMode.TWO_WAY,
            )
        )

        # Conversion display (read-only)
        self.add_binding(
            PropertyBinding(
                source_property="value",
                target_property="text",
                converter=ConversionDisplayConverter(self.unit),
                mode=BindingMode.ONE_WAY,
            ),
            target_element="conversion_label",
        )

    def create_element(self) -> Any:
        with ui.column().classes("w-full"):
            # Main input
            number_kwargs = {
                "value": 0,
                "suffix": "°C" if self.unit == "celsius" else "°F",
                "step": 0.1,
                "precision": 1,
            }
            temp_input = ui.number(**number_kwargs).classes("w-full")

            # Conversion display
            self.conversion_label = ui.label("").classes("text-sm text-gray-500")
            self._ui_element_refs["conversion_label"] = self.conversion_label

        return temp_input


# Custom converters for temperature widget
class UnitConversionConverter(BindingConverter):
    """Converter for temperature unit conversion"""

    def __init__(self, unit: str):
        self.unit = unit

    def to_view(self, celsius_value: Any) -> float:
        """Convert stored Celsius to display unit"""
        # Unwrap if needed
        if hasattr(celsius_value, "value"):
            celsius_value = celsius_value.value

        if celsius_value is None:
            return 0.0

        if self.unit == "celsius":
            return celsius_value
        else:  # fahrenheit
            return (celsius_value * 9 / 5) + 32

    def to_model(self, display_value: float) -> float:
        """Convert display unit back to Celsius for storage"""
        if self.unit == "celsius":
            return display_value
        else:  # fahrenheit
            return (display_value - 32) * 5 / 9


class ConversionDisplayConverter(BindingConverter):
    """Converter for showing the alternate unit"""

    def __init__(self, primary_unit: str):
        self.primary_unit = primary_unit

    def to_view(self, celsius_value: Any) -> str:
        """Format conversion display text"""
        # Unwrap if needed
        if hasattr(celsius_value, "value"):
            celsius_value = celsius_value.value

        if celsius_value is None:
            return ""

        if self.primary_unit == "celsius":
            fahrenheit = (celsius_value * 9 / 5) + 32
            return f"({fahrenheit:.1f}°F)"
        else:
            return f"({celsius_value:.1f}°C)"
