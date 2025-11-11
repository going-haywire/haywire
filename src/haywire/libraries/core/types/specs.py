"""
Built-in data type specifications for Haywire core library.
"""

from haywire.core.data.specs import DataPortSpec
from haywire.core.data.enums import DataType, DataContainerType

# ============================================================================
# Numeric Types
# ============================================================================

INT = DataPortSpec(
    key='core:int',
    data_type=DataType.INT,
    data_container=DataContainerType.SINGLE,
    label='Integer',
    description='Whole number',
    color='#f7b0ff',
    icon='tag',
    widget='core:number.widget',
    value=0,
)

FLOAT = DataPortSpec(
    key='core:float',
    data_type=DataType.FLOAT,
    data_container=DataContainerType.SINGLE,
    label='Float',
    description='Decimal number',
    color='#50b0ff',
    icon='circle',
    widget='core:number.widget',
    value=0.0,
)

# ============================================================================
# Text Types
# ============================================================================

STRING = DataPortSpec(
    key='core:string',
    data_type=DataType.STRING,
    data_container=DataContainerType.SINGLE,
    label='String',
    description='Text data',
    color='#ffc107',
    icon='type',
    widget='core:text.input.widget',
    value='',
)

# ============================================================================
# Boolean Type
# ============================================================================

BOOL = DataPortSpec(
    key='core:bool',
    data_type=DataType.BOOL,
    data_container=DataContainerType.SINGLE,
    label='Boolean',
    description='True or False',
    color='#4caf50',
    icon='checkbox',
    widget='core:checkbox.widget',
    value=False,
)

# ============================================================================
# Binary Type
# ============================================================================

BYTES = DataPortSpec(
    key='core:bytes',
    data_type=DataType.BYTES,
    data_container=DataContainerType.SINGLE,
    label='Bytes',
    description='Binary data',
    color='#9e9e9e',
    icon='file',
    widget=None,
    value=b'',
)

# ============================================================================
# Collection Types
# ============================================================================

LIST = DataPortSpec(
    key='core:list',
    data_type=DataType.LIST,
    data_container=DataContainerType.LIST,
    label='List',
    description='Ordered collection',
    color='#e91e63',
    icon='list',
    widget=None,
    value=[],
)

DICT = DataPortSpec(
    key='core:dict',
    data_type=DataType.DICT,
    data_container=DataContainerType.DICT,
    label='Dictionary',
    description='Key-value pairs',
    color='#9c27b0',
    icon='map',
    widget=None,
    value={},
)
