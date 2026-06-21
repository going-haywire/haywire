"""Benchmark case registry for ``haywire-benchmark``.

Each case is a plain callable that *prepares* a benchmark (builds its frozen
graph/nodes, returns a zero-arg ``run`` to time). The runner (``run.py``) handles
warmup, min-of-N timing, stamping, and storage — cases here stay pure so the same
registry can be imported by the perf smoke test.

Every case reports **nanoseconds per operation**, where one "operation" is one
node execution (graph cases) or one isolated call (micro cases). All inputs are
frozen (``benchmarks/graphs/`` + ``haybale_testing/nodes/benchmark/``) so a moved
number means the *framework* moved — see ``benchmarks/README.md``.

The library system must already be bootstrapped (the runner does this) before a
case's ``prepare`` runs; cases use the global graph API like the tests do.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

_FROZEN_GRAPH = Path(__file__).resolve().parent / "graphs" / "loop_bench.haywire"
_LOOP_END = 1000  # ForLoop bound for the frozen loop graph (~3000 node execs/run)


@dataclass
class Prepared:
    """The runnable a case hands back to the runner."""

    run: Callable[[], None]  # one timed iteration
    ops: int  # operations per run() call (node execs, or inner-loop count)
    repeats: int  # N for min-of-N
    warmup: int


@dataclass
class Case:
    name: str
    category: str  # "graph" | "micro"
    unit: str  # always "ns" (per operation) for now
    prepare: Callable[[], Prepared]


# ---------------------------------------------------------------------------
# graph case: nodes-in-context (the real loop graph)
# ---------------------------------------------------------------------------
def _prepare_graph_loop() -> Prepared:
    from haywire.core.assembly.flow_assembly_manager import FlowAssemblyManager
    from haywire.core.execution.event_source import Trigger
    from haywire.core.execution.vm import HaywireVM
    from haywire.core.graph.base import BaseGraph

    graph = BaseGraph(graph_id="bench_loop", name="bench loop")
    assert graph.load_from_file(str(_FROZEN_GRAPH)), f"failed to load {_FROZEN_GRAPH}"
    for nw in graph.node_wrappers.values():
        if "ForLoop" in nw.node.identity.registry_key and "end" in nw.node.ports:
            nw.node.ports["end"].set_value(_LOOP_END)
    graph.force_validation()

    flows = FlowAssemblyManager().assemble_graph(graph)
    vm = HaywireVM()

    def _fire(flow) -> int:
        trig = Trigger(source_key=flow.get_subscription_key(), payload={}, timestamp=0.0)
        return vm.execute_control_flow(flow, trig)

    flow = max(flows, key=_fire)  # the loop flow has the most node execs
    node_count = _fire(flow)

    def run() -> None:
        _fire(flow)

    return Prepared(run=run, ops=node_count, repeats=15, warmup=5)


# ---------------------------------------------------------------------------
# micro case: bare node dispatch (_execute with no ports/edges)
# ---------------------------------------------------------------------------
def _prepare_node_execute_bare() -> Prepared:
    from haybale_testing.nodes.benchmark.bench_bare_node import BenchBareNode

    from haywire.core.execution.execution_context import ExecutionContext
    from haywire.core.graph.base import BaseGraph

    graph = BaseGraph(graph_id="bench_bare", name="bench bare")
    nw = graph.create_node_wrapper(BenchBareNode.class_identity.registry_key, position=(0, 0))
    graph.force_validation()

    node = nw.node
    ctx = ExecutionContext(global_ctx={}, local_ctx={})
    inner = 2000

    def run() -> None:
        for _ in range(inner):
            node._execute(ctx)

    return Prepared(run=run, ops=inner, repeats=15, warmup=5)


CASES: List[Case] = [
    Case("graph_loop", "graph", "ns", _prepare_graph_loop),
    Case("node_execute_bare", "micro", "ns", _prepare_node_execute_bare),
]


def get_cases(only: Optional[str] = None) -> List[Case]:
    """All cases, or those whose name contains ``only`` (case-name filter)."""
    if only is None:
        return list(CASES)
    return [c for c in CASES if only in c.name]
