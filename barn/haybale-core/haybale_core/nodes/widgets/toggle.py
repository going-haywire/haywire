"""Toggle."""

from haybale_core.nodes.widgets.base import BaseWidgetNode
from haywire.api import BOOL, TOGGLE_WIDGET, NodeType, node


@node(
    label="Toggle",
    description="An on/off switch that sends true or false, and shows the value it is fed",
    menu="core/widgets/toggle",
    search_tags=["toggle", "switch", "bool", "boolean", "widget", "control", "stage"],
    node_type=NodeType.DATA,
)
class ToggleNode(BaseWidgetNode):
    """An on/off switch that sends true or false.

    A value arriving at *In* flips the switch and is sent on. Last write wins, so a
    fed switch is a display: flipping it sends a value that lasts until the next one
    arrives. When the feeding edge goes, the switch keeps its last value.
    """

    value_type = BOOL
    widget_key = TOGGLE_WIDGET
    default_value = False
