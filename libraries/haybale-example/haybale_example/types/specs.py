# Custom data type for testing
from haywire.core.data.enums import FlowType
from haywire.core.types.decorators import primitive_type
from haywire.libraries.core.types.specs import FLOAT


@primitive_type(
    registry_id='temperature',
    label='Temperature',
    description='Temperature data type',
    widget='example:widget:temperature.widget',
    ui={'properties': {'unit': '°D'}}
)
class Temperature(FLOAT):
    """
    Temperature measurement type.
    
    A specialized float type for representing temperature values with
    a custom widget for temperature input/display.
    
    **Inherits:** FLOAT: Base float type (value: float, cls=float)
    
    **widget** = 'example:widget:temperature.widget' - Temperature-specific input control
    
    **ui** = {'properties': {'unit': '°D'}} - Display unit for temperature values
    
    Usage:
        Temperature.as_inlet('temp', default=25.0)
        Temperature.as_outlet('result')
    
    Note: This class inherits the 'value: float' field from FLOAT.
    No need to redefine it - the decorator auto-extracts cls=float from FLOAT.
    """
    pass
