"""Nested-fold probe — proves fold() nests to any depth."""

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType


@node(
    label="Nested Fold",
    description="Tests that folds nest",
    search_tags=["testing", "fold"],
    menu="testing/testbed",
    node_type=NodeType.DATA,
)
class NestedFoldNode(BaseNode):
    """Test-only."""

    def init(self):
        from haywire.barn.builtin.types import FLOAT, STRING

        self.add(STRING.as_outlet("out"))
        with self.fold("Solver"):
            self.add(FLOAT.as_config("substeps", default=10.0))
            with self.fold("Interpolation Range"):
                self.add(FLOAT.as_config("begin", default=0.0))
                self.add(FLOAT.as_config("end", default=1.0))

    def worker(self, context: ExecutionContext) -> str | None:
        return None
