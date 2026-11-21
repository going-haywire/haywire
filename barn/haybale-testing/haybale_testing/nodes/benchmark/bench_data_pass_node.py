"""FROZEN benchmark node — DO NOT EDIT.

Used by the ``graph_data_chain_*`` benchmarks (see ``benchmarks/cases.py``): one link of
a 32-node data chain. Editing it shifts the baseline; add a new frozen node instead.
"""

from haywire.api import FLOAT, BaseNode, ExecutionContext, NodeType, node


@node(
    label="Bench Data Pass",
    description="FROZEN: data node passing x + 1 on, for measuring data-flow evaluation.",
    menu="testing/benchmark",
    search_tags=["benchmark", "frozen", "data", "chain"],
    node_type=NodeType.DATA,
)
class BenchDataPassNode(BaseNode):
    """One FLOAT inlet `x`, one FLOAT outlet `y = x + 1`."""

    def init(self):
        self.add(FLOAT.as_inlet("x", default=0.0))
        self.add(FLOAT.as_outlet("y"))

    def worker(self, context: ExecutionContext, x: float) -> str | None:
        self.out("y", x + 1.0)
        return None
