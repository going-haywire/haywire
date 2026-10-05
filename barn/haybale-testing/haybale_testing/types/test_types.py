"""
Temperature type - derived from FLOAT for testing type hierarchy support.
"""

from dataclasses import dataclass

from haywire.core.types import type, BaseType
from haywire.core.types import PrimitiveType, PrimitiveField
from haywire.barn.builtin.wires import CallbackWire, DataWire
from haywire.barn.builtin.types import INT, STRING
from haybale_testing.wires import TestVisualWire

# ============================================================================
# Numeric Types
# ============================================================================


@type(
    wire_type=DataWire,
    label="Integer",
    description="Whole number",
    color="#f7b0ff",
    default={"value": 0},
)
class TEST_INT(PrimitiveType[int]):
    """Integer data type"""

    def to_dict(self) -> dict:
        return {"value": int(self._value)}

    @classmethod
    def from_dict(cls, data: dict) -> int:
        return int(data.get("value", 0))


# define INTField for INT type to guarantee integer storage
class TEST_INTField(PrimitiveField):
    """DataField for TEST_INT type storing integer values"""

    def _set_own(self, value):
        self._value = int(value)


# Set field_class attributes after classes are defined
TEST_INT.field_class = TEST_INTField

# ============================================================================


@type(
    wire_type=DataWire,
    label="Float",
    description="Decimal numberer",
    color="#50b0ff",
    default={"value": 0.0},
)
class TEST_FLOAT(PrimitiveType[float]):
    """Float data type"""

    def to_dict(self) -> dict:
        return {"value": float(self._value)}

    @classmethod
    def from_dict(cls, data: dict) -> float:
        return float(data.get("value", 0.0))


# define FLOATField for FLOAT type to guarantee float storage
class TEST_FLOATField(PrimitiveField):
    """DataField for FLOAT type storing float values"""

    def _set_own(self, value):
        self._value = float(value)


# Set field_class attributes after classes are defined
TEST_FLOAT.field_class = TEST_FLOATField

# ============================================================================
# Text Types
# ============================================================================


@type(
    wire_type=DataWire,
    label="String",
    description="Text data",
    color="#ffc107",
    default={"value": ""},
)
class TEST_STRING(PrimitiveType[str]):
    """String data type"""

    def to_dict(self) -> dict:
        return {"value": str(self._value)}

    @classmethod
    def from_dict(cls, data: dict) -> str:
        return str(data.get("value", ""))


# ============================================================================
# Boolean Type
# ============================================================================


@type(
    wire_type=DataWire,
    label="Boolean",
    description="True or False",
    color="#4caf50",
    default={"value": False},
)
class TEST_BOOL(PrimitiveType[bool]):
    """Boolean data type"""

    def to_dict(self) -> dict:
        return {"value": bool(self._value)}

    @classmethod
    def from_dict(cls, data: dict) -> bool:
        return bool(data.get("value", False))


@type(
    label="Temperature",
    description="Temperature in Celsius",
    color="#ff5722",
    wire_type=DataWire,
    default={"value": 20.0},
)
class TEST_TEMPERATURE(TEST_FLOAT):
    """Temperature in Celsius — derived from TEST_FLOAT."""

    pass


# Reuse TEST_FLOATField to guarantee float storage
TEST_TEMPERATURE.field_class = TEST_FLOATField


# ============================================================================
# Callback Types
# ============================================================================


@type(
    wire_type=CallbackWire,
    label="Test Record Callback",
    description="Test callback subscription carried as a dataclass",
    default=None,
    color="#ff3c00",
)
@dataclass
class TEST_RECORD_CALLBACK(BaseType):
    """Test-only callback type whose subscription is a dataclass: a name plus a weight."""

    name: str = ""
    weight: int = 0


# ============================================================================
# Drawn-only Types
# ============================================================================


@type(
    wire_type=TestVisualWire,
    label="Test Visual",
    description="Test-only: a text value on a drawn-only wire",
    color="#8e8e8e",
)
class TEST_VISUAL(STRING):
    """Test-only type on `TestVisualWire`, with `STRING`'s text widget."""


@type(
    wire_type=TestVisualWire,
    label="Test Visual Count",
    description="Test-only: a number on a drawn-only wire",
    color="#8e8e8e",
)
class TEST_VISUAL_COUNT(INT):
    """Test-only type on `TestVisualWire` whose payload differs from `TEST_VISUAL`'s."""
