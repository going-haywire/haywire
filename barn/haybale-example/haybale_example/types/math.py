# Custom data type for testing
from __future__ import annotations

from enum import Enum

from haywire.api import STRING, type


class MathOPs(Enum):
    ADD = "add"
    SUBTRACT = "subtract"
    MULTIPLY = "multiply"
    DIVIDE = "divide"

    @classmethod
    def values(cls):
        return [e.value for e in cls]

    @classmethod
    def names(cls):
        return [e.name for e in cls]


@type(
    label="Math Operation",
    description="Simple mathematical operations for one or two float values",
    widget_key="haywire-core:widget:MenuWidget",
    widget_config={"properties": {"options": MathOPs.values()}},
    default=MathOPs.ADD.value,
)
class MATH_OPERATION(STRING):
    """A custom type representing simple mathematical operations."""

    pass
