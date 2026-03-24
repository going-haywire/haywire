# Custom data type for testing
from haywire.core.types.decorator import type
from haybale_core.types.specs import FLOAT


@type(
    registry_id="temperature",
    label="Temperature",
    description="Temperature data types",
    widget_key="example:widget:TemperatureWidget",
    widget_config={"properties": {"unit": "°D"}},
)
class Temperature(FLOAT):
    """
    Temperature measurement type.

    A specialized float type for representing temperature values with
    a custom widget for temperature input/display.

    **Inherits:** FLOAT: Base float type (value: float, cls=float)

    **widget_key** = 'example:widget:TemperatureWidget' - Temperature-specific input control

    **widget_config** = {'properties': {'unit': '°D'}} - Display unit for temperature values

    Usage:
        Temperature.as_inlet('temp', default=25.0)
        Temperature.as_outlet('result')

    Note: This class inherits the 'value: float' field from FLOAT.
    No need to redefine it - the decorator auto-extracts cls=float from FLOAT.
    """

    pass
