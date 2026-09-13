"""Inlet-only fold probe — one direction is fine, and nests.

The nested fold is the interesting half: a fold is spec'd ``as_config`` and
only takes its direction when its block closes, so a naive implementation
rejects it from an inlet parent as a direction clash.
"""

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType


@node(
    label="Inlet Fold",
    description="Tests that a fold of only inlets is fine, and that folds nest inside it",
    search_tags=["testing", "fold"],
    menu="testing/testbed",
    node_type=NodeType.DATA,
)
class InletFoldNode(BaseNode):
    """Test-only."""

    def init(self):
        from haywire.barn.builtin.types import FLOAT, STRING

        self.add(STRING.as_outlet("out"))
        with self.fold("Input as"):
            self.add(FLOAT.as_inlet("a"))
            with self.fold("Input bs"):
                self.add(FLOAT.as_inlet("b"))

    def worker(self, context: ExecutionContext) -> str | None:
        return None
