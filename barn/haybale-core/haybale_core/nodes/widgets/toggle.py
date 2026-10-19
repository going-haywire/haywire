"""Toggle."""

from haybale_core.nodes.widgets.base import WidgetNode
from haywire.barn.builtin.types import BOOL
from haywire.barn.builtin.widget_keys import SWITCH_WIDGET
from haywire.core.node import NodeType, node


@node(
    label="Toggle",
    description="An on/off switch that sends true or false, and shows the value it is fed",
    menu="core/widgets/toggle",
    search_tags=["toggle", "switch", "bool", "boolean", "widget", "control", "stage"],
    node_type=NodeType.DATA,
)
class ToggleNode(WidgetNode):
    """An on/off switch that sends true or false.

    A value arriving at *In* flips the switch and is sent on. Last write wins, so a
    fed switch is a display: flipping it sends a value that lasts until the next one
    arrives. When the feeding edge goes, the switch keeps its last value.
    """

    value_type = BOOL
    widget_key = SWITCH_WIDGET
    default_value = False
