from haywire.core.node import node, BaseNode, NodeType
from haywire.core.execution.execution_context import ExecutionContext
from haybale_core.types import FLOAT, STRING


@node(
    label="Display",
    description="Displays input values for debugging",
    search_tags=["display", "debug", "output", "basic"],
    menu="testing/testbed",
    node_type=NodeType.DATA,
)
class DisplayNode(BaseNode):
    """Node that displays input values"""

    def init(self):
        # Configure UI
        self.props.skin = "example:skin:ExampleNodeSkin"

        # Using the new .as_inlet() API
        self.add(FLOAT.as_inlet("a", label="Value A", default=10.0, widget_key="core:widget:NumberWidget"))
        self.add(FLOAT.as_inlet("b", label="Value B", default=3.4, widget_key="core:widget:NumberWidget"))
        self.add(
            STRING.as_inlet(
                "operation", label="Operation", default="add", widget_key="core:widget:TextWidget"
            )
        )
        self.add(FLOAT.as_outlet("result", label="Result"))

    def worker(self, context: ExecutionContext) -> str | None:
        """Execute the node - display the input value"""
        return None
