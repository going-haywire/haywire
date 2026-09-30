from haywire.barn.builtin import widget_keys
from haywire.core.types import FlowType, PrimitiveField, PrimitiveType, type


# ============================================================================
# Numeric Types
# ============================================================================


@type(
    flow_type=FlowType.DATA,
    label="Integer",
    description="Whole number",
    color="#f7b0ff",
    default={"value": 0},
    widget_key=widget_keys.NUMBER_WIDGET,
)
class INT(PrimitiveType[int]):
    """Integer data type"""

    def to_dict(self) -> dict:
        return {"value": int(self._value)}

    @classmethod
    def from_dict(cls, data: dict) -> int:
        return int(data.get("value", 0))


# define INTField for INT type to guarantee integer storage
class INTField(PrimitiveField):
    """DataField for INT type storing integer values.

    Coerces on EVERY write, so an INT-typed setting or port silently truncates
    a float: ``bag.count = 3.7`` stores ``3``. That is a real behavioural
    difference from ``setting[FLOAT]``, and the reason ``OPTIONAL[INT]`` derives
    its field class from this one rather than using a plain ``PrimitiveField``
    — an optional int must behave exactly like a plain int while a value is
    present. ``int(None)`` raises, so the wrapper's absence branch bypasses this
    override (see ``_absence_tolerant_field``).
    """

    def _set_own(self, value):
        self._value = int(value)


# Set field_class attributes after classes are defined
INT.field_class = INTField

# ============================================================================


@type(
    flow_type=FlowType.DATA,
    label="Float",
    description="Decimal numberer",
    color="#50b0ff",
    default={"value": 0.0},
    widget_key=widget_keys.NUMBER_WIDGET,
)
class FLOAT(PrimitiveType[float]):
    """Float data type"""

    def to_dict(self) -> dict:
        return {"value": float(self._value)}

    @classmethod
    def from_dict(cls, data: dict) -> float:
        return float(data.get("value", 0.0))


# define FLOATField for FLOAT type to guarantee float storage
class FLOATField(PrimitiveField):
    """DataField for FLOAT type storing float values"""

    def _set_own(self, value):
        self._value = float(value)


# Set field_class attributes after classes are defined
FLOAT.field_class = FLOATField

# ============================================================================
# Text Types
# ============================================================================


@type(
    flow_type=FlowType.DATA,
    label="String",
    description="Text data",
    color="#ffc107",
    default={"value": ""},
    widget_key=widget_keys.TEXT_WIDGET,
)
class STRING(PrimitiveType[str]):
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
    flow_type=FlowType.DATA,
    label="Boolean",
    description="True or False",
    color="#4caf50",
    default={"value": False},
    widget_key=widget_keys.SWITCH_WIDGET,
)
class BOOL(PrimitiveType[bool]):
    """Boolean data type"""

    def to_dict(self) -> dict:
        return {"value": bool(self._value)}

    @classmethod
    def from_dict(cls, data: dict) -> bool:
        return bool(data.get("value", False))
