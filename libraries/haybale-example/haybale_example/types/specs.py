# Custom data type for testing
from haywire.core.data.enums import ContainerType
from haywire.core.data.specs import specs_factory

from haywire.libraries.core.types.specs import FLOAT

TEMPERATURE = FLOAT(
    id='temperature',
    key='example:temperature',
    label='Temperature',
    description='Temperature data type',
    widget='example:temperature.widget',
    ui={'properties': {'unit': '°D'}}
)