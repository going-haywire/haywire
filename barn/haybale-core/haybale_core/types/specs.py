"""
Built-in data type specifications for Haywire core library.
"""

from haywire.core.types import type, FlowType, PrimitiveType, PrimitiveField, BaseType


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
class GROUP(PrimitiveType[bool]):
    """Group data type"""

    @classmethod
    def to_dict(cls, value: bool) -> dict:
        return {"value": bool(value)}

    @classmethod
    def from_dict(cls, data: dict) -> bool:
        return bool(data.get("value", False))

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

    @classmethod
    def to_dict(cls, value: int) -> dict:
        return {"value": int(value)}

    @classmethod
    def from_dict(cls, data: dict) -> int:
        return int(data.get("value", 0))

# define INTField for INT type to guarantee integer storage
class INTField(PrimitiveField):
    """DataField for INT type storing integer values"""
    def set_value(self, value, source_id = None):
        value = int(value)
        return super().set_value(value, source_id)

# Set field_class attributes after classes are defined
INT.field_class = INTField

# ============================================================================

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

    @classmethod
    def to_dict(cls, value: float) -> dict:
        return {"value": float(value)}

    @classmethod
    def from_dict(cls, data: dict) -> float:
        return float(data.get("value", 0.0))
    
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

    @classmethod
    def to_dict(cls, value: str) -> dict:
        return {"value": str(value)}

    @classmethod
    def from_dict(cls, data: dict) -> str:
        return str(data.get("value", ""))
    
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

    @classmethod
    def to_dict(cls, value: bool) -> dict:
        return {"value": bool(value)}

    @classmethod
    def from_dict(cls, data: dict) -> bool:
        return bool(data.get("value", False))
    

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

    @classmethod
    def to_dict(cls, value: bytes) -> dict:
        import base64
        return {"value": base64.b64encode(value).decode('ascii')}

    @classmethod
    def from_dict(cls, data: dict) -> bytes:
        import base64
        return base64.b64decode(data.get("value", ""))

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

    @classmethod
    def to_dict(cls, value: list) -> dict:
        return {"value": list(value)}

    @classmethod
    def from_dict(cls, data: dict) -> list:
        return list(data.get("value", []))

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

    @classmethod
    def to_dict(cls, value: dict) -> dict:
        return {"value": dict(value)}

    @classmethod
    def from_dict(cls, data: dict) -> dict:
        return dict(data.get("value", {}))

# ============================================================================
# Exec Types
# ============================================================================

@type(
    registry_id='exec',
    flow_type=FlowType.CONTROL,
    label='Execution Signal',
    description='Signal for controlling execution flow between nodes',
    color="#004cff",
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
    default={},
)
class CALLBACK(STRING):
    """
    callback signal type - represents callback flow
    Inherits from STRING for payload compatibility.
    """
