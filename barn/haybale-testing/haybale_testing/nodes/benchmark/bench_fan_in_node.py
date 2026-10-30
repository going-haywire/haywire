"""FROZEN benchmark node — DO NOT EDIT.

Used by the ``graph_data_chain_*`` benchmarks (see ``benchmarks/cases.py``): joins two
branches of the chain. Editing it shifts the baseline; add a new frozen node instead.
"""

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode, NodeType, node


@node(
    label="Bench Fan In Node",
    description="FROZEN: data node adding two inputs, for measuring a fan-in in data-flow evaluation.",
    menu="testing/benchmark",
    search_tags=["benchmark", "frozen", "data", "fan-in"],
    node_type=NodeType.DATA,
)
class BenchFanInNode(BaseNode):
    """FLOAT inlets `a` and `b`, FLOAT outlet `y = a + b`."""

    def init(self):
        from haywire.barn.builtin.types import FLOAT

        self.add(FLOAT.as_inlet("a", default=0.0))
        self.add(FLOAT.as_inlet("b", default=0.0))
        self.add(FLOAT.as_outlet("y"))

    def worker(self, context: ExecutionContext, a: float, b: float) -> str | None:
        self.out("y", a + b)
        return None
