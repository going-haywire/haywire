"""Nested fold probe — a fold holds ports, not other folds, so this raises."""

from __future__ import annotations

from haywire.api import FLOAT, STRING, BaseNode, ExecutionContext, NodeType, node


@node(
    label="Nested Fold Probe",
    description="Tests that a fold declared inside another fold raises",
    search_tags=["testing", "fold"],
    menu="testing/testbed",
    node_type=NodeType.DATA,
)
class NestedFoldProbeNode(BaseNode):
    """Test-only."""

    def init(self):
        self.add(STRING.as_outlet("out"))
        with self.fold("Outer"):
            self.add(FLOAT.as_config("substeps", default=10.0))
            with self.fold("Inner"):
                self.add(FLOAT.as_config("begin", default=0.0))

    def worker(self, context: ExecutionContext) -> str | None:
        return None
