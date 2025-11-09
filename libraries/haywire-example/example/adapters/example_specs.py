# Custom data type for testing
from haywire.core.data.enums import DataContainerType, DataType
from haywire.core.data.specs import specs_factory

TEMPERATURE = specs_factory(
    id='TEMPERATURE',
    label='Temperature',
    description='Temperature data type',
    type=DataType.FLOAT,
    container=DataContainerType.SINGLE,
    widget='example:temperature.widget',
    ui={'properties': {'unit': '°C'}}
)