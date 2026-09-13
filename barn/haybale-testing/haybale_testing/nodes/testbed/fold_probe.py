"""Fold probe — every shape a fold is allowed to take, on one node.

Three sibling folds: a config fold, an inlet fold (so the lane a fold renders
in is exercised, not just the config band), and one that starts closed.
"""

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType


@node(
    label="Fold Probe",
    description="Tests fold minting, lanes and open state",
    search_tags=["testing", "fold", "render"],
    menu="testing/rendering",
    node_type=NodeType.DATA,
)
class FoldProbeNode(BaseNode):
    """Test-only."""

    def init(self):
        from haywire.barn.builtin.types import FLOAT, STRING

        self.add(STRING.as_outlet("out"))

        with self.fold("Solver", description="How the solver steps through time."):
            self.add(FLOAT.as_config("substeps", default=10.0))

        # No description=, so the tooltip shows FOLD's own.
        with self.fold("Inputs"):
            self.add(FLOAT.as_inlet("a"))
            self.add(FLOAT.as_inlet("b"))

        with self.fold("Advanced", default=False):
            self.add(FLOAT.as_config("epsilon", default=1e-6))

    def worker(self, context: ExecutionContext) -> str | None:
        return None
