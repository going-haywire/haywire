"""
Built-in data type specifications for Haywire core library.
"""

from haywire.core.data.specs import DataPortSpec
from haywire.core.data.enums import ContainerType

# ============================================================================
# Numeric Types
# ============================================================================

INT = DataPortSpec(
    id='int',
    key='core:int',
    cls_type=int,
    container_type=ContainerType.SINGLE,
    label='Integer',
    description='Whole number',
    color='#f7b0ff',
    icon='tag',
    widget='core:number.widget',
    default=0,
)

FLOAT = DataPortSpec(
    id='float',
    key='core:float',
    cls_type=float,
    container_type=ContainerType.SINGLE,
    label='Float',
    description='Decimal number',
    color='#50b0ff',
    icon='circle',
    widget='core:number.widget',
    default=0.0,
)

# ============================================================================
# Text Types
# ============================================================================

STRING = DataPortSpec(
    id='string',
    key='core:string',
    cls_type=str,
    container_type=ContainerType.SINGLE,
    label='String',
    description='Text data',
    color='#ffc107',
    icon='type',
    widget='core:text.input.widget',
    default='',
)

# ============================================================================
# Boolean Type
# ============================================================================

BOOL = DataPortSpec(
    id='bool',
    key='core:bool',
    cls_type=bool,
    container_type=ContainerType.SINGLE,
    label='Boolean',
    description='True or False',
    color='#4caf50',
    icon='checkbox',
    widget='core:checkbox.widget',
    default=False,
)

# ============================================================================
# Binary Type
# ============================================================================

BYTES = DataPortSpec(
    id='bytes',
    key='core:bytes',
    cls_type=bytes,
    container_type=ContainerType.SINGLE,
    label='Bytes',
    description='Binary data',
    color='#9e9e9e',
    icon='file',
    widget=None,
    default=b'',
)

# ============================================================================
# Collection Types
# ============================================================================

LIST = DataPortSpec(
    id='list',
    key='core:list',
    cls_type=list,
    container_type=ContainerType.LIST,
    label='List',
    description='Ordered collection',
    color='#e91e63',
    icon='list',
    widget=None,
    default=[],
)

DICT = DataPortSpec(
    id='dict',
    key='core:dict',
    cls_type=dict,
    container_type=ContainerType.DICT,
    label='Dictionary',
    description='Key-value pairs',
    color='#9c27b0',
    icon='map',
    widget=None,
    default={},
)
