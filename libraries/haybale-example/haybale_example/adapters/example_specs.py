# Custom data type for testing
from haywire.core.data.enums import DataContainerType
from haywire.core.data.specs import specs_factory

TEMPERATURE = specs_factory(
    id='temperature',
    key='example:temperature',
    label='Temperature',
    description='Temperature data type',
    value_type=float,
    data_container=DataContainerType.SINGLE,
    widget='example:temperature.widget',
    ui={'properties': {'unit': '°C'}}
)