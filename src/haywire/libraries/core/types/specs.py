"""
Built-in data type specifications for Haywire core library.
"""

from haywire.core.data.specs import DataPortSpec
from haywire.core.data.enums import DataContainerType

# ============================================================================
# Numeric Types
# ============================================================================

INT = DataPortSpec(
    id='int',
    key='core:int',
    value_type=int,
    data_container=DataContainerType.SINGLE,
    label='Integer',
    description='Whole number',
    color='#f7b0ff',
    icon='tag',
    widget='core:number.widget',
    value=0,
)

FLOAT = DataPortSpec(
    id='float',
    key='core:float',
    value_type=float,
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
    id='string',
    key='core:string',
    value_type=str,
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
    id='bool',
    key='core:bool',
    value_type=bool,
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
    id='bytes',
    key='core:bytes',
    value_type=bytes,
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
    id='list',
    key='core:list',
    value_type=list,
    data_container=DataContainerType.LIST,
    label='List',
    description='Ordered collection',
    color='#e91e63',
    icon='list',
    widget=None,
    value=[],
)

DICT = DataPortSpec(
    id='dict',
    key='core:dict',
    value_type=dict,
    data_container=DataContainerType.DICT,
    label='Dictionary',
    description='Key-value pairs',
    color='#9c27b0',
    icon='map',
    widget=None,
    value={},
)
