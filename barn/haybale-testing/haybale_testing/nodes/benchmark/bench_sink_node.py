"""FROZEN benchmark node — DO NOT EDIT.

Used by ``graph_data_chain_*`` and ``graph_loop_half_failing`` (see
``benchmarks/cases.py``): the control node whose localized data flow the benchmarks
evaluate. Editing it shifts the baseline; add a new frozen node instead.
"""

from __future__ import annotations

from haywire.api import EXEC, FLOAT, BaseNode, ExecutionContext, NodeType, node


@node(
    label="Bench Sink",
    description="FROZEN: control node with one data inlet, ending the branch.",
    menu="testing/benchmark",
    search_tags=["benchmark", "frozen", "control", "sink"],
    node_type=NodeType.CONTROL,
)
class BenchSinkNode(BaseNode):
    """EXEC inlet `exec_in` and FLOAT data inlet `x`; the worker ends the branch."""

    def init(self):
        self.add(EXEC.as_inlet("exec_in"))
        self.add(FLOAT.as_inlet("x", default=0.0))

    def worker(self, context: ExecutionContext, x: float) -> str | None:
        return None
