"""FROZEN benchmark node — DO NOT EDIT.

Used by the ``node_execute_bare`` micro-benchmark (see ``benchmarks/cases.py``).
Its purpose is to measure the pure per-node dispatch cost of ``BaseNode._execute``
— dirty-resolution (empty) → ``on_validate`` → executor → ``worker`` → result
parse — with no ports and no edges, so the number reflects framework overhead
only. Changing this node silently shifts the benchmark baseline, which defeats
drift detection; if a new bench needs different ports, add a new frozen node
instead of editing this one.
"""

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType


@node(
    label="Bench Bare Node",
    description="FROZEN: minimal no-port control node for measuring _execute dispatch overhead.",
    menu="testing/benchmark",
    search_tags=["benchmark", "frozen", "bare", "dispatch"],
    node_type=NodeType.CONTROL,
)
class BenchBareNode(BaseNode):
    """A control node with no ports whose worker does nothing and returns None.

    The full ``_execute`` path still runs (no early-out, since it is not a data
    node), so calling ``node._execute(ctx)`` in a tight loop measures dispatch.
    """

    def init(self):
        # Intentionally no ports — pure dispatch.
        pass

    def worker(self, context: ExecutionContext) -> str | None:
        return None
