"""FROZEN benchmark node — DO NOT EDIT.

Used by ``graph_loop_half_failing`` (see ``benchmarks/cases.py``): a data node that
raises on odd input, so every other loop iteration fails. Editing it shifts the
baseline; add a new frozen node instead.
"""

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode, NodeType, node


class BenchOddFailure(Exception):
    """The exception the benchmark node raises on odd input."""


@node(
    label="Bench Loop Raise Node",
    description="FROZEN: data node raising on odd input, for measuring a loop with failures.",
    menu="testing/benchmark",
    search_tags=["benchmark", "frozen", "data", "raise", "loop"],
    node_type=NodeType.DATA,
)
class BenchLoopRaiseNode(BaseNode):
    """FLOAT inlet `x`, FLOAT outlet `y = x`; raises when `x` is odd."""

    def init(self):
        from haywire.barn.builtin.types import FLOAT

        self.add(FLOAT.as_inlet("x", default=0.0))
        self.add(FLOAT.as_outlet("y"))

    def worker(self, context: ExecutionContext, x: float) -> str | None:
        if int(x) % 2:
            raise BenchOddFailure("odd input")
        self.out("y", x)
        return None
