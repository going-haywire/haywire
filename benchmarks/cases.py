"""Benchmark case registry for ``haywire-benchmark``.

Each case is a plain callable that *prepares* a benchmark (builds its graph/nodes,
returns a zero-arg ``run`` to time). The runner (``run.py``) handles warmup,
min-of-N timing, stamping, and storage — cases here stay pure so the same registry
can be imported by the perf smoke test.

Every case reports **nanoseconds per operation**, where one "operation" is one
node execution (graph cases) or one isolated call (micro cases). Graph cases build
their topology fresh from an explicit node-key + edge list (deterministic, but
tracking the live registry so a moved node/type can't rot a frozen file); frozen
nodes live in ``haybale_testing/nodes/benchmark/``. A moved number means the
*framework* moved — see ``benchmarks/README.md``.

The library system must already be bootstrapped (the runner does this) before a
case's ``prepare`` runs; cases use the global graph API like the tests do.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional

_LOOP_END = 1000  # ForLoop bound for the loop graph (~3000 node execs/run)

# Edges of the loop benchmark graph, keyed by the short node ids assigned in
# _build_loop_graph. Port ids are part of each node's public API.
_LOOP_EDGES: list[tuple[str, str, str, str]] = [
    # (source_node_id, outlet_port, sink_node_id, inlet_port)
    ("BeginPlay", "exec", "TickEmit", "start"),
    ("TickEvent", "listen_callback", "TickEmit", "callback_names"),
    ("TickEvent", "exec", "ForLoop", "execute"),
    ("ForLoop", "loop_body", "ControlSwitch", "exec"),
    ("ForLoop", "index", "MathOP", "value_a"),
    ("ForLoop", "index", "MathOP", "value_b"),
    ("MathOP", "result", "ControlSwitch", "with"),
    ("Shutdown", "exec", "TickEmit", "stop"),
    ("MathOP", "result", "Print", "message"),
    ("ControlSwitch", "true", "Print", "exec"),
]


def _build_loop_graph():
    """Construct the loop benchmark graph fresh via the public graph API.

    Node types are referenced by their *class* (resolved to a registry_key at build
    time) rather than a hardcoded key string: if a node moves library or is renamed,
    this fails at import with a clear error instead of silently producing a stale key
    that no longer resolves — the exact failure mode a frozen .haywire file had when
    the primitive types were hoisted into the `builtin` library.
    """
    from haybale_core.nodes.emits.tick_emit import TickEmitNode
    from haybale_core.nodes.events.begin_play import BeginPlayNode
    from haybale_core.nodes.events.shutdown import ShutdownNode
    from haybale_core.nodes.events.tick_event import TickEventNode
    from haybale_core.nodes.for_loop import ForLoopNode
    from haybale_core.nodes.print_terminal import PrintTerminalMessageNode
    from haybale_core.nodes.switch import ControlSwitch
    from haybale_example.nodes.math_op import MathOP

    from haywire.core.graph.base import BaseGraph

    # (stable short id -> node class). The short id keys _LOOP_EDGES and stays fixed
    # even if the class's registry_key changes.
    node_classes = {
        "BeginPlay": BeginPlayNode,
        "TickEmit": TickEmitNode,
        "TickEvent": TickEventNode,
        "ForLoop": ForLoopNode,
        "ControlSwitch": ControlSwitch,
        "MathOP": MathOP,
        "Print": PrintTerminalMessageNode,
        "Shutdown": ShutdownNode,
    }

    graph = BaseGraph(graph_id="bench_loop", name="bench loop")
    ids: dict[str, str] = {}
    for short_id, node_cls in node_classes.items():
        key = node_cls.class_identity.registry_key
        nw = graph.create_node_wrapper(key, position=(0, 0))
        assert nw is not None, f"failed to create benchmark node {node_cls.__name__} ({key!r})"
        ids[short_id] = nw.node_id
    for src, outlet, sink, inlet in _LOOP_EDGES:
        graph.create_edge_wrapper(ids[src], outlet, ids[sink], inlet)
    return graph


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

    graph = _build_loop_graph()
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
