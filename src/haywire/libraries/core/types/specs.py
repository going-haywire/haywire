"""
Built-in data type specifications for Haywire core library.
"""

from haywire.core.types.decorators import type_
from haywire.core.types.base import TypeBase
from haywire.core.data.enums import ContainerType, FlowType

# ============================================================================
# Exec Types
# ============================================================================

@type_(
    registry_id='exec',
    cls=None,
    container_type=ContainerType.SINGLE,
    flow_type=FlowType.CTRL,
    label='Execution Signal',
    description='Signal for controlling execution flow between nodes',
    color='#ff9800',
    icon='flash',
    widget=None,
    default=None,
)
class EXEC(TypeBase):
    """Execution signal type for controlling node execution flow"""
    pass


@type_(
    registry_id='callback',
    cls=None,
    container_type=ContainerType.SINGLE,
    flow_type=FlowType.CALLBACK,
    label='Callback Signal',
    description='Signal for callback execution between nodes',
    color='#ff5722',
    icon='repeat',
    widget=None,
    default=None,
)
class CALLBACK(TypeBase):
    """Callback signal type for callback execution between nodes"""
    pass


# ============================================================================
# Numeric Types
# ============================================================================

@type_(
    registry_id='int',
    cls=int,
    container_type=ContainerType.SINGLE,
    label='Integer',
    description='Whole number',
    color='#f7b0ff',
    icon='tag',
    widget='core:number.widget',
    default=0,
)
class INT(TypeBase):
    """Integer data type"""
    pass


@type_(
    registry_id='float',
    cls=float,
    container_type=ContainerType.SINGLE,
    flow_type=FlowType.DATA,
    label='Float',
    description='Decimal number',
    color='#50b0ff',
    icon='circle',
    widget='core:number.widget',
    default=0.0,
)
class FLOAT(TypeBase):
    """Float data type"""
    pass


# ============================================================================
# Text Types
# ============================================================================

@type_(
    registry_id='string',
    cls=str,
    container_type=ContainerType.SINGLE,
    flow_type=FlowType.DATA,
    label='String',
    description='Text data',
    color='#ffc107',
    icon='type',
    widget='core:text.input.widget',
    default='',
)
class STRING(TypeBase):
    """String data type"""
    pass


# ============================================================================
# Boolean Type
# ============================================================================

@type_(
    registry_id='bool',
    cls=bool,
    container_type=ContainerType.SINGLE,
    flow_type=FlowType.DATA,
    label='Boolean',
    description='True or False',
    color='#4caf50',
    icon='checkbox',
    widget='core:checkbox.widget',
    default=False,
)
class BOOL(TypeBase):
    """Boolean data type"""
    pass


# ============================================================================
# Binary Type
# ============================================================================

@type_(
    registry_id='bytes',
    cls=bytes,
    container_type=ContainerType.SINGLE,
    flow_type=FlowType.DATA,
    label='Bytes',
    description='Binary data',
    color='#9e9e9e',
    icon='file',
    widget=None,
    default=b'',
)
class BYTES(TypeBase):
    """Bytes data type"""
    pass


# ============================================================================
# Collection Types
# ============================================================================

@type_(
    registry_id='list',
    cls=list,
    container_type=ContainerType.LIST,
    flow_type=FlowType.DATA,
    label='List',
    description='Ordered collection',
    color='#e91e63',
    icon='list',
    widget=None,
    default=[],
)
class LIST(TypeBase):
    """List data type"""
    pass


@type_(
    registry_id='dict',
    cls=dict,
    container_type=ContainerType.DICT,
    flow_type=FlowType.DATA,
    label='Dictionary',
    description='Key-value pairs',
    color='#9c27b0',
    icon='map',
    widget=None,
    default={},
)
class DICT(TypeBase):
    """Dictionary data type"""
    pass

