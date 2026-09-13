"""Nested-closed-fold probe — a closed outer fold hides a nested fold child."""

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType


@node(
    label="Nested Closed",
    description="Tests that a closed outer fold hides a nested fold child",
    search_tags=["testing", "fold"],
    menu="testing/testbed",
    node_type=NodeType.DATA,
)
class NestedClosedFoldNode(BaseNode):
    """Test-only."""

    def init(self):
        from haywire.barn.builtin.types import FLOAT, STRING

        self.add(STRING.as_outlet("out"))
        with self.fold("Solver", default=False):
            with self.fold("Interpolation Range"):
                self.add(FLOAT.as_config("begin", default=0.0))

    def worker(self, context: ExecutionContext) -> str | None:
        return None
