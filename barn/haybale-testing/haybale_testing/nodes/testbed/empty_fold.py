"""Empty fold probe — a fold with nothing inside has no direction to take."""

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType


@node(
    label="Empty Fold",
    description="Tests that a fold holding no ports raises",
    search_tags=["testing", "fold"],
    menu="testing/testbed",
    node_type=NodeType.DATA,
)
class EmptyFoldNode(BaseNode):
    """Test-only."""

    def init(self):
        from haywire.barn.builtin.types import STRING

        self.add(STRING.as_outlet("out"))
        with self.fold("Nothing"):
            pass

    def worker(self, context: ExecutionContext) -> str | None:
        return None
