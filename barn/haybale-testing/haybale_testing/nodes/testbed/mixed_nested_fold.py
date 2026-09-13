"""Mixed nested fold probe — a nested fold must match its parent's direction.

A fold takes its direction late, so the check that a nested fold agrees with
its parent happens when the inner block closes rather than when it is added.
"""

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType


@node(
    label="Mixed Nested Fold",
    description="Tests that a config fold inside an inlet fold raises",
    search_tags=["testing", "fold"],
    menu="testing/testbed",
    node_type=NodeType.DATA,
)
class MixedNestedFoldNode(BaseNode):
    """Test-only."""

    def init(self):
        from haywire.barn.builtin.types import FLOAT, STRING

        self.add(STRING.as_outlet("out"))
        with self.fold("Outer"):
            self.add(FLOAT.as_inlet("an_inlet"))
            with self.fold("Inner"):
                self.add(FLOAT.as_config("a_config"))

    def worker(self, context: ExecutionContext) -> str | None:
        return None
