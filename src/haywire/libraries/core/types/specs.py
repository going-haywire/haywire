"""
Built-in data type specifications for Haywire core library.
"""

from dataclasses import dataclass
from haywire.core.types.decorators import primitive_type
from haywire.core.types.base import PrimitiveType
from haywire.core.data.enums import ContainerType, FlowType

# ============================================================================
# Exec Types
# ============================================================================

@primitive_type(
    registry_id='exec',
    container_type=ContainerType.SINGLE,
    flow_type=FlowType.CTRL,
    label='Execution Signal',
    description='Signal for controlling execution flow between nodes',
    color='#ff9800',
    icon='flash',
    widget=None,
    default=None,
)
class EXEC(PrimitiveType):
    """Execution signal type for controlling node execution flow"""
    value: None = None


@primitive_type(
    registry_id='callback',
    container_type=ContainerType.SINGLE,
    flow_type=FlowType.CALLBACK,
    label='Callback Signal',
    description='Signal for callback execution between nodes',
    color='#ff5722',
    icon='repeat',
    widget=None,
    default=None,
)
class CALLBACK(PrimitiveType):
    """Callback signal type for callback execution between nodes"""
    value: None = None


# ============================================================================
# Numeric Types
# ============================================================================

@primitive_type(
    registry_id='int',
    container_type=ContainerType.SINGLE,
    label='Integer',
    description='Whole number',
    color='#f7b0ff',
    icon='tag',
    widget='core:widget:number.widget',
    default=0,
)
@dataclass
class INT(PrimitiveType):
    """Integer data type"""
    test: int

@primitive_type(
    registry_id='float',
    container_type=ContainerType.SINGLE,
    flow_type=FlowType.DATA,
    label='Float',
    description='Decimal numbers',
    color='#50b0ff',
    icon='circle',
    widget='core:widget:number.widget',
    default=0.0,
)
@dataclass
class FLOAT(PrimitiveType):
    """Float data type"""
    value: float


# ============================================================================
# Text Types
# ============================================================================

@primitive_type(
    registry_id='string',
    container_type=ContainerType.SINGLE,
    flow_type=FlowType.DATA,
    label='String',
    description='Text data',
    color='#ffc107',
    icon='type',
    widget='core:widget:text.input.widget',
    default='',
)
@dataclass
class STRING(PrimitiveType):
    """String data type"""
    value: str


# ============================================================================
# Boolean Type
# ============================================================================

@primitive_type(
    registry_id='bool',
    container_type=ContainerType.SINGLE,
    flow_type=FlowType.DATA,
    label='Boolean',
    description='True or False',
    color='#4caf50',
    icon='checkbox',
    widget='core:widget:checkbox.widget',
    default=False,
)
@dataclass
class BOOL(PrimitiveType):
    """Boolean data type"""
    value: bool


# ============================================================================
# Binary Type
# ============================================================================

@primitive_type(
    registry_id='bytes',
    container_type=ContainerType.SINGLE,
    flow_type=FlowType.DATA,
    label='Bytes',
    description='Binary data',
    color='#9e9e9e',
    icon='file',
    widget=None,
    default=b'',
)
@dataclass
class BYTES(PrimitiveType):
    """Bytes data type"""
    value: bytes


# ============================================================================
# Collection Types
# ============================================================================

@primitive_type(
    registry_id='list',
    container_type=ContainerType.LIST,
    flow_type=FlowType.DATA,
    label='List',
    description='Ordered collection',
    color='#e91e63',
    icon='list',
    widget=None,
    default=[],
)
@dataclass
class LIST(PrimitiveType):
    """List data type"""
    value: list


@primitive_type(
    registry_id='dict',
    container_type=ContainerType.DICT,
    flow_type=FlowType.DATA,
    label='Dictionary',
    description='Key-value pairs',
    color='#9c27b0',
    icon='map',
    widget=None,
    default={},
)
@dataclass
class DICT(PrimitiveType):
    """Dictionary data type"""
    value: dict
