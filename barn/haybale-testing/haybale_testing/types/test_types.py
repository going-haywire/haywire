"""
Temperature type - derived from FLOAT for testing type hierarchy support.
"""

from haywire.core.types import type, FlowType
from haywire.core.types import PrimitiveType, PrimitiveField

# ============================================================================
# Numeric Types
# ============================================================================


@type(
    flow_type=FlowType.DATA,
    label="Integer",
    description="Whole number",
    color="#f7b0ff",
    default={"value": 0},
)
class TEST_INT(PrimitiveType[int]):
    """Integer data type"""

    @classmethod
    def to_dict(cls, value: int) -> dict:
        return {"value": int(value)}

    @classmethod
    def from_dict(cls, data: dict) -> int:
        return int(data.get("value", 0))


# define INTField for INT type to guarantee integer storage
class TEST_INTField(PrimitiveField):
    """DataField for TEST_INT type storing integer values"""

    def set_value(self, value, source_id=None):
        value = int(value)
        return super().set_value(value, source_id)


# Set field_class attributes after classes are defined
TEST_INT.field_class = TEST_INTField

# ============================================================================


@type(
    flow_type=FlowType.DATA,
    label="Float",
    description="Decimal numberer",
    color="#50b0ff",
    default={"value": 0.0},
)
class TEST_FLOAT(PrimitiveType[float]):
    """Float data type"""

    @classmethod
    def to_dict(cls, value: float) -> dict:
        return {"value": float(value)}

    @classmethod
    def from_dict(cls, data: dict) -> float:
        return float(data.get("value", 0.0))


# define FLOATField for FLOAT type to guarantee float storage
class TEST_FLOATField(PrimitiveField):
    """DataField for FLOAT type storing float values"""

    def set_value(self, value, source_id=None):
        value = float(value)
        return super().set_value(value, source_id)


# Set field_class attributes after classes are defined
TEST_FLOAT.field_class = TEST_FLOATField

# ============================================================================
# Text Types
# ============================================================================


@type(
    flow_type=FlowType.DATA,
    label="String",
    description="Text data",
    color="#ffc107",
    default={"value": ""},
)
class TEST_STRING(PrimitiveType[str]):
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
    flow_type=FlowType.DATA,
    label="Boolean",
    description="True or False",
    color="#4caf50",
    default={"value": False},
)
class TEST_BOOL(PrimitiveType[bool]):
    """Boolean data type"""

    @classmethod
    def to_dict(cls, value: bool) -> dict:
        return {"value": bool(value)}

    @classmethod
    def from_dict(cls, data: dict) -> bool:
        return bool(data.get("value", False))


@type(
    label="Temperature",
    description="Temperature in Celsius",
    color="#ff5722",
    flow_type=FlowType.DATA,
    default={"value": 20.0},
)
class TEST_TEMPERATURE(TEST_FLOAT):
    """Temperature in Celsius — derived from TEST_FLOAT."""

    pass


# Reuse TEST_FLOATField to guarantee float storage
TEST_TEMPERATURE.field_class = TEST_FLOATField
