"""Reorder probe — static and dynamic ports for port-ordering tests."""

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode, NodeType, node


@node(
    label="Reorder Probe",
    description="Tests user-driven port ordering",
    search_tags=["testing", "reorder", "order"],
    menu="testing/testbed",
    node_type=NodeType.DATA,
)
class ReorderProbeNode(BaseNode):
    """Test-only.

    Static inlets `a`, `b`, `c` and outlet `out`, plus the dynamic inlets
    `dyn_a`, `dyn_b`, `dyn_c` that `rebuild()` re-adds through `rejig()`.
    """

    def init(self):
        from haywire.barn.builtin.types import FLOAT, STRING

        self.add(FLOAT.as_inlet("a"))
        self.add(FLOAT.as_inlet("b"))
        self.add(FLOAT.as_inlet("c"))
        self.add(STRING.as_outlet("out"))
        self.rebuild()

    def rebuild(self):
        """Re-add the dynamic inlets, as post_init would on every load."""
        from haywire.barn.builtin.types import FLOAT

        with self.rejig(include=r"^dyn_"):
            for name in ("dyn_a", "dyn_b", "dyn_c"):
                self.add(FLOAT.as_inlet(name))

    def worker(self, context: ExecutionContext) -> str | None:
        return None
