"""Float Slider and Int Slider."""

from typing import Any

from haybale_core.nodes.widgets.base import WidgetNode
from haywire.barn.builtin.types import FLOAT, INT
from haywire.barn.builtin.widget_keys import SLIDER_WIDGET
from haywire.core.node import NodeType, node
from haywire.core.settings import NodeSettings, setting


@node(
    label="Float Slider",
    description="A slider that sends a decimal number, and shows the one it is fed",
    menu="core/widgets/float_slider",
    search_tags=["float", "slider", "widget", "control", "stage"],
    node_type=NodeType.DATA,
)
class FloatSliderNode(WidgetNode):
    """A slider that sends a decimal number from Min to Max.

    A value arriving at *In* moves the slider and is sent on. Last write wins, so a
    fed slider is a display: dragging it sends a value that lasts until the next one
    arrives. When the feeding edge goes, the slider keeps its last value.

    *Min*, *Max* and *Step* can be promoted to inlets. Nothing clamps the value: one
    outside the range is sent on unchanged.
    """

    value_type = FLOAT
    widget_key = SLIDER_WIDGET
    default_value = 0.0
    config_bag = "range"

    class range(NodeSettings):
        min = setting[FLOAT](0.0, label="Min", description="The slider's left end")
        max = setting[FLOAT](1.0, label="Max", description="The slider's right end")
        step = setting[FLOAT](0.01, label="Step", description="The smallest change the slider makes")

    def _widget_properties(self) -> dict[str, Any]:
        return {"min": self.range.min, "max": self.range.max, "step": self.range.step}


@node(
    label="Int Slider",
    description="A slider that sends a whole number, and shows the one it is fed",
    menu="core/widgets/int_slider",
    search_tags=["int", "integer", "slider", "widget", "control", "stage"],
    node_type=NodeType.DATA,
)
class IntSliderNode(WidgetNode):
    """A slider that sends a whole number from Min to Max.

    A value arriving at *In* moves the slider and is sent on. Last write wins, so a
    fed slider is a display: dragging it sends a value that lasts until the next one
    arrives. When the feeding edge goes, the slider keeps its last value.

    *Min*, *Max* and *Step* can be promoted to inlets. Nothing clamps the value: one
    outside the range is sent on unchanged.
    """

    value_type = INT
    widget_key = SLIDER_WIDGET
    default_value = 0
    config_bag = "range"

    class range(NodeSettings):
        min = setting[INT](0, label="Min", description="The slider's left end")
        max = setting[INT](100, label="Max", description="The slider's right end")
        step = setting[INT](1, label="Step", description="The smallest change the slider makes")

    def _widget_properties(self) -> dict[str, Any]:
        return {"min": self.range.min, "max": self.range.max, "step": self.range.step}
