from typing import Any
from nicegui import ui


from haybale_core.types import FLOAT, INT
from haywire.ui.widget.base import BaseWidget
from haywire.ui.widget.converters import BindingConverter, Converters
from haywire.ui.widget.decorator import widget

from haybale_example.types.specs import Temperature


@widget(description="Number widget with range clamping", compatible_types=[FLOAT, INT])
class ValidatedNumberWidget(BaseWidget):
    """Number widget with range validation and custom formatting"""

    def build(self) -> Any:
        props = self._config.get("properties", {})
        el = ui.number(
            value=0,
            label=props.get("label", ""),
            min=props.get("min"),
            max=props.get("max"),
            step=props.get("step", 1),
            precision=props.get("precision"),
            prefix=props.get("prefix", ""),
            suffix=props.get("suffix", ""),
        ).classes("w-full")
        min_val = props.get("min")
        max_val = props.get("max")
        if min_val is not None or max_val is not None:
            return self.bind(
                el,
                converter=Converters.chain(
                    Converters.primitive(default_value=0),
                    Converters.range(min_value=min_val, max_value=max_val, clamp=True),
                ),
            )
        return self.bind(el)


@widget(description="Temperature with unit conversion", compatible_types=[Temperature])
class TemperatureWidget(BaseWidget):
    """
    Temperature widget demonstrating:
    - Custom converter for unit conversion
    - Multiple UI elements with separate bindings
    - Read-only conversion display
    """

    def __init__(self, port) -> None:
        super().__init__(port)
        self.unit = self._config.get("properties", {}).get("unit", "celsius")

    def build(self) -> Any:
        with ui.column().classes("w-full") as root:
            temp_input = ui.number(
                value=0,
                suffix="°C" if self.unit == "celsius" else "°F",
                step=0.1,
                precision=1,
            ).classes("w-full")
            self.bind(temp_input, converter=UnitConversionConverter(self.unit))

            label = ui.label("").classes("text-sm text-gray-500")
            self.bind(label, prop="text", one_way=True, converter=ConversionDisplayConverter(self.unit))
        return root


# Custom converters for temperature widget
class UnitConversionConverter(BindingConverter):
    """Converter for temperature unit conversion"""

    def __init__(self, unit: str):
        self.unit = unit

    def to_view(self, model_value: Any) -> float:
        """Convert stored Celsius to display unit"""
        # Unwrap if needed
        if hasattr(model_value, "value"):
            model_value = model_value.value

        if model_value is None:
            return 0.0

        if self.unit == "celsius":
            return model_value
        else:  # fahrenheit
            return (model_value * 9 / 5) + 32

    def to_model(self, view_value: float) -> float:
        """Convert display unit back to Celsius for storage"""
        if self.unit == "celsius":
            return view_value
        else:  # fahrenheit
            return (view_value - 32) * 5 / 9


class ConversionDisplayConverter(BindingConverter):
    """Converter for showing the alternate unit"""

    def __init__(self, primary_unit: str):
        self.primary_unit = primary_unit

    def to_view(self, model_value: Any) -> str:
        """Format conversion display text"""
        # Unwrap if needed
        if hasattr(model_value, "value"):
            model_value = model_value.value

        if model_value is None:
            return ""

        if self.primary_unit == "celsius":
            fahrenheit = (model_value * 9 / 5) + 32
            return f"({fahrenheit:.1f}°F)"
        else:
            return f"({model_value:.1f}°C)"
