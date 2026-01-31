"""
Built-in data type specifications for Haywire core library.
"""

from haywire.core.data.fields import PrimitiveField
from haywire.core.types.base import PrimitiveType
from haywire.core.types.decorator import type
from haywire.core.types.base import BaseType
from haywire.core.data.enums import FlowType


# ============================================================================
# Group Type
# ============================================================================

@type(
    registry_id='group',
    flow_type=FlowType.DATA,
    label='Group',
    description='Inlet group',
    color="#ebff0f",
    widget_key='core:widget:SwitchWidget',
    default={'value': False},
)
class GROUP(PrimitiveType[int]):
    """Group data type"""
    pass

# ============================================================================
# Numeric Types
# ============================================================================

@type(
    registry_id='int',
    flow_type=FlowType.DATA,
    label='Integer',
    description='Whole number',
    color='#f7b0ff',
    default={'value': 0},
)
class INT(PrimitiveType[int]):
    """Integer data type"""
    pass

# define INTField for INT type to guarantee integer storage
class INTField(PrimitiveField):
    """DataField for INT type storing integer values"""
    def set_value(self, value, source_id = None):
        value = int(value)
        return super().set_value(value, source_id)

# Set field_class attributes after classes are defined
INT.field_class = INTField

@type(
    registry_id='float',
    flow_type=FlowType.DATA,
    label='Float',
    description='Decimal numberer',
    color='#50b0ff',
    default={'value': 0.0},
)
class FLOAT(PrimitiveType[float]):
    """Float data type"""
    pass

# define FLOATField for FLOAT type to guarantee float storage
class FLOATField(PrimitiveField):
    """DataField for FLOAT type storing float values"""
    def set_value(self, value, source_id = None):
        value = float(value)
        return super().set_value(value, source_id)

# Set field_class attributes after classes are defined
FLOAT.field_class = FLOATField

# ============================================================================
# Text Types
# ============================================================================

@type(
    registry_id='string',
    flow_type=FlowType.DATA,
    label='String',
    description='Text data',
    color='#ffc107',
    default={'value': ''},
)
class STRING(PrimitiveType[str]):
    """String data type"""
    pass


# ============================================================================
# Boolean Type
# ============================================================================

@type(
    registry_id='bool',
    flow_type=FlowType.DATA,
    label='Boolean',
    description='True or False',
    color='#4caf50',
    default={'value': False},
)
class BOOL(PrimitiveType[bool]):
    """Boolean data type"""
    pass


# ============================================================================
# Binary Type
# ============================================================================

@type(
    registry_id='bytes',
    flow_type=FlowType.DATA,
    label='Bytes',
    description='Binary data',
    color='#9e9e9e',
    default={'value': b''},
)
class BYTES(PrimitiveType[bytes]):
    """Bytes data type"""
    pass


# ============================================================================
# Collection Types
# ============================================================================

@type(
    registry_id='list',
    flow_type=FlowType.DATA,
    label='List',
    description='Ordered collection',
    color='#e91e63',
    default={'value': []},
)
class LIST(PrimitiveType[list]):
    """List data type"""
    pass

@type(
    registry_id='dict',
    flow_type=FlowType.DATA,
    label='Dictionary',
    description='Key-value pairs',
    color='#9c27b0',
    default={'value': {}},
)
class DICT(PrimitiveType[dict]):
    """Dictionary data type"""
    pass

# ============================================================================
# Exec Types
# ============================================================================

@type(
    registry_id='exec',
    flow_type=FlowType.CONTROL,
    label='Execution Signal',
    description='Signal for controlling execution flow between nodes',
    color="#004cff",
    widget=None,
    default={},
)
class EXEC(BaseType):
    """Execution signal type - represents execution flow, not data"""
    
    @classmethod
    def create_default(cls) -> 'EXEC':
        return cls()

# ============================================================================
# Callback Types
# ============================================================================


@type(
    registry_id='callback',
    flow_type=FlowType.CALLBACK,
    label='Callback Signal',
    description='Signal for callback execution between nodes',
    color="#ff3c00",
    widget=None,
    default={},
)
class CALLBACK(STRING):
    """
    callback signal type - represents callback flow, not data
    Inherits from STRING for payload compatibility.
    """
