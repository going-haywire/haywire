"""Node fixtures for the declared-size-box feature (browser test support).

One node per widget flavour, deliberately not one node with three ports: a
node's size floor is a whole-card property, so widgets sharing a node would
floor it together and the declaration under test would not be isolated.
"""

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType
from haywire.barn.builtin.types import STRING


class _SizeBoxNode(BaseNode):
    """Hosts one oversized-content widget, named by ``WIDGET_KEY``."""

    WIDGET_KEY: str = ""

    def init(self):
        self.add(
            STRING.as_config(
                "preview",
                label="Preview",
                default="",
                widget_key=self.WIDGET_KEY,
            )
        )
        # Data nodes must carry at least one data outlet (structural validation).
        self.add(STRING.as_outlet("passthrough", label="Passthrough"))

    def worker(self, context: ExecutionContext) -> str | None:
        return None


@node(
    label="Size Box (content-sized)",
    description="Hosts an oversized widget with no declared box",
    search_tags=["size", "resize", "widget", "testing"],
    menu="testing/testbed",
    node_type=NodeType.DATA,
)
class SizeBoxContentNode(_SizeBoxNode):
    WIDGET_KEY = "haybale-testing:widget:OversizedContentWidget"


@node(
    label="Size Box (declared width)",
    description="Hosts an oversized widget declaring min_width only",
    search_tags=["size", "resize", "widget", "testing"],
    menu="testing/testbed",
    node_type=NodeType.DATA,
)
class SizeBoxAspectNode(_SizeBoxNode):
    WIDGET_KEY = "haybale-testing:widget:AspectBoxWidget"


@node(
    label="Size Box (declared box)",
    description="Hosts an oversized widget declaring both axes",
    search_tags=["size", "resize", "widget", "testing"],
    menu="testing/testbed",
    node_type=NodeType.DATA,
)
class SizeBoxFixedNode(_SizeBoxNode):
    WIDGET_KEY = "haybale-testing:widget:FixedBoxWidget"
