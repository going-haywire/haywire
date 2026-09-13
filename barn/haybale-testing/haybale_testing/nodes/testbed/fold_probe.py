"""Fold probe — a node whose ports exercise fold()."""

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType


@node(
    label="Fold Probe",
    description="Tests fold() minting and nesting",
    search_tags=["testing", "fold"],
    menu="testing/testbed",
    node_type=NodeType.DATA,
)
class FoldProbeNode(BaseNode):
    """Test-only."""

    def init(self):
        from haywire.barn.builtin.types import FLOAT, STRING

        self.add(STRING.as_outlet("out"))
        with self.fold("Solver"):
            self.add(FLOAT.as_config("substeps", default=10.0))

    def worker(self, context: ExecutionContext) -> str | None:
        return None
