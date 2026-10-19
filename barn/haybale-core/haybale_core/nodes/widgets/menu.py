"""Menu."""

from typing import Any, cast

from haybale_core.keys import ARRAY_WIDGET
from haybale_core.nodes.widgets.base import WidgetNode
from haybale_core.types import ArrayType
from haywire.barn.builtin.types import CHOICES, STRING
from haywire.barn.builtin.widget_keys import SELECT_WIDGET
from haywire.core.node import NodeType, node
from haywire.core.settings import NodeSettings, setting


@node(
    label="Menu",
    description="A drop-down that sends the item picked, and shows the item it is fed",
    menu="core/widgets/menu",
    search_tags=["menu", "dropdown", "select", "choice", "widget", "control", "stage"],
    node_type=NodeType.DATA,
)
class MenuNode(WidgetNode):
    """A drop-down that sends the text of the item picked.

    Edit the items in *Options*; they can also be promoted to an inlet. A text
    arriving at *In* is shown and sent on, even one that is not among the options.
    Last write wins, so a fed menu is a display. When the feeding edge goes, the
    menu keeps its last item.
    """

    value_type = CHOICES
    inlet_type = STRING
    widget_key = SELECT_WIDGET
    default_value = "One"
    config_bag = "menu"

    class menu(NodeSettings):
        options = setting[ArrayType[STRING]](
            ["One", "Two", "Three"],
            label="Options",
            description="The items the menu offers, in order",
            widget={"key": ARRAY_WIDGET, "config": {"properties": {"item": {"commit": True}}}},
        )

    def _widget_properties(self) -> dict[str, Any]:
        return {"options": list(cast("list[str]", self.menu.options))}
