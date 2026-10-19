"""Float Number and Int Number."""

from typing import Any

from haybale_core.nodes.widgets.base import WidgetNode
from haywire.barn.builtin.types import FLOAT, INT, OPTIONAL
from haywire.barn.builtin.widget_keys import NUMBER_WIDGET
from haywire.core.node import NodeType, node
from haywire.core.settings import NodeSettings, setting


@node(
    label="Float Number",
    description="A number box that sends a decimal number, and shows the one it is fed",
    menu="core/widgets/float_number",
    search_tags=["float", "number", "value", "widget", "control", "stage"],
    node_type=NodeType.DATA,
)
class FloatNumberNode(WidgetNode):
    """A number box that sends a decimal number: drag it, or click and type.

    A value arriving at *In* shows in the box and is sent on. Last write wins, so a
    fed box is a display: a value typed into it lasts until the next one arrives.
    When the feeding edge goes, the box keeps its last value.

    *Min* and *Max* are unbounded until set. They and *Step* can be promoted to
    inlets. Nothing clamps the value: one outside the range is sent on unchanged.
    """

    value_type = FLOAT
    widget_key = NUMBER_WIDGET
    default_value = 0.0
    config_bag = "range"

    class range(NodeSettings):
        min = setting[OPTIONAL[FLOAT]](None, label="Min", description="The lowest value; none is unbounded")
        max = setting[OPTIONAL[FLOAT]](None, label="Max", description="The highest value; none is unbounded")
        step = setting[FLOAT](0.1, label="Step", description="How much one drag step or arrow changes it")

    def _widget_properties(self) -> dict[str, Any]:
        return {"min": self.range.min, "max": self.range.max, "step": self.range.step}


@node(
    label="Int Number",
    description="A number box that sends a whole number, and shows the one it is fed",
    menu="core/widgets/int_number",
    search_tags=["int", "integer", "number", "value", "widget", "control", "stage"],
    node_type=NodeType.DATA,
)
class IntNumberNode(WidgetNode):
    """A number box that sends a whole number: drag it, or click and type.

    A value arriving at *In* shows in the box and is sent on. Last write wins, so a
    fed box is a display: a value typed into it lasts until the next one arrives.
    When the feeding edge goes, the box keeps its last value.

    *Min* and *Max* are unbounded until set. They and *Step* can be promoted to
    inlets. Nothing clamps the value: one outside the range is sent on unchanged.
    """

    value_type = INT
    widget_key = NUMBER_WIDGET
    default_value = 0
    config_bag = "range"

    class range(NodeSettings):
        min = setting[OPTIONAL[INT]](None, label="Min", description="The lowest value; none is unbounded")
        max = setting[OPTIONAL[INT]](None, label="Max", description="The highest value; none is unbounded")
        step = setting[INT](1, label="Step", description="How much one drag step or arrow changes it")

    def _widget_properties(self) -> dict[str, Any]:
        return {"min": self.range.min, "max": self.range.max, "step": self.range.step}
