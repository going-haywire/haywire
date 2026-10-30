"""FROZEN benchmark node — DO NOT EDIT.

Used by ``graph_data_chain_root_fails`` and ``node_execute_raises`` (see
``benchmarks/cases.py``): a data node whose worker always raises. Editing it shifts the
baseline; add a new frozen node instead.
"""

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode, NodeType, node


class BenchFailure(Exception):
    """The exception the benchmark node raises."""


@node(
    label="Bench Data Raise Node",
    description="FROZEN: data node whose worker always raises, for measuring the failure path.",
    menu="testing/benchmark",
    search_tags=["benchmark", "frozen", "data", "raise", "failure"],
    node_type=NodeType.DATA,
)
class BenchDataRaiseNode(BaseNode):
    """One FLOAT inlet `x`, one FLOAT outlet `y`; the worker raises every time."""

    def init(self):
        from haywire.barn.builtin.types import FLOAT

        self.add(FLOAT.as_inlet("x", default=0.0))
        self.add(FLOAT.as_outlet("y"))

    def worker(self, context: ExecutionContext, x: float) -> str | None:
        raise BenchFailure("bench failure")
