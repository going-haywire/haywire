from haybale_core.types import FLOAT, INT
from haywire.ui.widget.base import BaseWidget
from haywire.ui.widget.converters import PrimitiveUnwrappingConverter
from haywire.ui.widget.decorator import widget
from nicegui import ui


from typing import Any


# --8<-- [start:knob_widget]
@widget(description="knob widget", compatible_types=[FLOAT, INT])
class KnobWidget(BaseWidget):
    """
    Rotary knob widget for numeric ports.

    Config options (via ``KnobWidget.config(properties={...})``):

    - ``min`` (int | float): Minimum value.
    - ``max`` (int | float): Maximum value.
    - ``step`` (int | float): Step increment.
    - ``color`` (str): Quasar color name for the knob arc (e.g. ``'primary'``, ``'green'``).
    - ``size`` (str): CSS size of the knob element (e.g. ``'60px'``).

    Example::

        KnobWidget.config(properties={'min': 0, 'max': 360, 'step': 1, 'color': 'teal'})
    """

    def build(self) -> Any:
        props = self._config.get("properties", {})
        with ui.row().classes("w-full justify-center text-xs"):
            knob = ui.knob(
                value=0,
                show_value=True,
                min=props.get("min", 0),
                max=props.get("max", 1),
                step=props.get("step", 0.01),
                color=props.get("color", "primary"),
                size=props.get("size", "60px"),
            )
        return self.bind(
            knob.classes("w-32 h-32"),
            converter=PrimitiveUnwrappingConverter(default_value=0.0),
        )


# --8<-- [end:knob_widget]
