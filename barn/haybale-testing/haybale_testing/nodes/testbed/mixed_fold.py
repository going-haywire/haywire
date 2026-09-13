"""Mixed-direction fold probe — must raise at declaration time."""

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType


@node(
    label="Mixed Fold",
    description="Tests that a fold spanning two directions raises",
    search_tags=["testing", "fold"],
    menu="testing/testbed",
    node_type=NodeType.DATA,
)
class MixedFoldNode(BaseNode):
    """Test-only."""

    def init(self):
        from haywire.barn.builtin.types import FLOAT, STRING

        self.add(STRING.as_outlet("out"))
        with self.fold("Mixed"):
            self.add(FLOAT.as_inlet("an_inlet"))
            self.add(FLOAT.as_outlet("an_outlet"))

    def worker(self, context: ExecutionContext) -> str | None:
        return None
