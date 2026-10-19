"""Text."""

from haybale_core.nodes.widgets.base import WidgetNode
from haywire.barn.builtin.types import STRING
from haywire.barn.builtin.widget_keys import TEXT_WIDGET
from haywire.core.node import NodeType, node


@node(
    label="Text",
    description="A text field that sends its text on Enter, and shows the text it is fed",
    menu="core/widgets/text",
    search_tags=["text", "string", "field", "widget", "control", "stage"],
    node_type=NodeType.DATA,
)
class TextNode(WidgetNode):
    """A text field that sends its text when you press Enter or leave the field.

    Nothing is sent while you type, so a consumer never sees a half-typed value. A
    text arriving at *In* shows in the field and is sent on. Last write wins, so a
    fed field is a display. When the feeding edge goes, the field keeps its last text.
    """

    value_type = STRING
    widget_key = TEXT_WIDGET
    default_value = ""
    base_properties = {"commit": True}
