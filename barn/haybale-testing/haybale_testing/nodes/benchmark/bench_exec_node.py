"""FROZEN benchmark node — DO NOT EDIT.

Used by the ``control_edge_forward`` micro-benchmark (see ``benchmarks/cases.py``).
Two of these wired ``exec_out → exec_in`` form one propagating EXEC edge; the
benchmark times ``HaywireVM._fallback_control_payload`` over that edge (the eager
pipe + adapter pull that carries a control payload). Minimal on purpose — a single
EXEC inlet/outlet — so the number reflects the control-edge machinery, not node
work. Editing it shifts the baseline; add a new frozen node instead.
"""

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType


@node(
    label="Bench Exec Node",
    description="FROZEN: minimal EXEC in→out conduit for measuring control-edge payload forwarding.",
    menu="testing/benchmark",
    search_tags=["benchmark", "frozen", "exec", "conduit", "control-edge"],
    node_type=NodeType.CONTROL,
)
class BenchExecNode(BaseNode):
    """Single EXEC inlet/outlet pass-through. Worker only advances."""

    def init(self):
        from haybale_core.types import EXEC

        self.add(EXEC.as_inlet("exec_in"))
        self.add(EXEC.as_outlet("exec_out"))

    def worker(self, context: ExecutionContext) -> str | None:
        return "exec_out"
