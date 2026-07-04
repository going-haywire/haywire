"""COLOR IType — a distinct str subclass so a color port is type-separable from STRING.

The color picker widget is wired in Plan 2 (widget unification); Plan 1 only
establishes the type.
"""

from haywire.barn.builtin import widget_keys
from haywire.core.types import FlowType, PrimitiveType
from haywire.core.types import type as type_decorator


class ColorStr(str):
    """Hex/rgba color string. A str subclass so COLOR != STRING at the type level."""


@type_decorator(
    flow_type=FlowType.DATA,
    label="Color",
    description="Hex or rgba color string",
    color="#f7b0ff",
    default={"value": "#ffffff"},
    widget_key=widget_keys.COLOR_WIDGET,
)
class COLOR(PrimitiveType[ColorStr]):
    """Color data type."""

    def to_dict(self) -> dict:
        return {"value": str(self._value)}

    @classmethod
    def from_dict(cls, data: dict) -> ColorStr:
        return ColorStr(data.get("value", "#ffffff"))
