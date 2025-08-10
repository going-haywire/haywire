# Custom data type for testing
from haywire.core.data.enums import DataCategory, DataType
from haywire.core.data.specs import specs_factory

TEMPERATURE = specs_factory(
    id='TEMPERATURE',
    label='Temperature',
    description='Temperature data type',
    type=DataType.FLOAT,
    category=DataCategory.SCALAR,
    widget='example.temperature',
    ui={'properties': {'unit': '°C'}}
)