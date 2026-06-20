"""Performance baseline for the EXEC-edge control-payload machinery.

Why this exists
---------------
Since ``c5298502`` ("new EXEC Control Edges carry now values") every CONTROL
edge builds an adapter chain and carries a payload (the EXEC type also became a
``PrimitiveType[dict]``), and the VM forwards it via
``HaywireVM._fallback_control_payload``. That cost a per-node regression vs
``v0.0.16``. This test pins a reproducible baseline so improvements to the
control-edge path can be measured against it.

It drives the real ``graphs/loop.haywire`` graph (the one the author benchmarks
in the app) so the numbers line up with hand-run measurements. VM-direct runs a
few percent leaner than the threaded scheduler harness, but the *fallback delta*
matches the app within noise.

Two design points, both learned the hard way:

1. **The fallback is injected, not relied upon.** The ``_fallback_control_payload``
   call in ``vm.py`` may be commented out in the working tree. So instead of
   trusting the VM's call site, the bench neutralises it and re-injects the real
   helper through a wrapper around ``_execute_control_node``. ``with_fallback``
   ON/OFF is therefore controlled entirely here, independent of source state, and
   both arms pay the identical wrapper overhead.
2. **Per-node averages are diluted.** In this graph only ~67% of node executions
   fire a control outlet (ForLoop re-enters via the loopback stack with a None
   inlet → cheap; MathOP is a pure data node → no fallback at all). A per-node
   number therefore buries the control-edge cost ~1.5x. The bench also reports
   the cost per *propagating* control edge (a firing entered through a real
   inlet), which is the undiluted signal to optimise against.

Informational only (``perf`` marker, excluded from the default run). Run with::

    uv run pytest -m perf tests/core/test_execution/test_control_payload_perf.py -s
"""

import haywire.core.graph.editor  # noqa: F401  (import first, per CLAUDE.md)

import statistics
import time
from pathlib import Path

import pytest

from haywire.core.assembly.flow_assembly_manager import FlowAssemblyManager
from haywire.core.execution.event_source import Trigger
from haywire.core.execution.flow import Flow
from haywire.core.execution.vm import HaywireVM
from haywire.core.graph.base import BaseGraph

pytestmark = [pytest.mark.perf, pytest.mark.integration]

_GRAPH = "graphs/loop.haywire"
_LOOP_END = 1000  # ForLoop bound → ~3000 node executions per flow run
_REPEATS = 11
_WARMUP = 4

# Captured at import: the *current* fallback implementation. Re-injected below so
# the bench measures it even when vm.py's call site is commented out, and tracks
# whatever optimised version lands later.
_REAL_FALLBACK = HaywireVM._fallback_control_payload


def _load_loop_graph() -> BaseGraph:
    root = Path(__file__).resolve()
    while not (root / _GRAPH).exists():
        if root == root.parent:
            pytest.skip(f"{_GRAPH} not found")
        root = root.parent

    graph = BaseGraph(graph_id="loop_perf", name="loop perf baseline")
    assert graph.load_from_file(str(root / _GRAPH)), f"failed to load {_GRAPH}"

    for nw in graph.node_wrappers.values():
        if "ForLoop" in nw.node.identity.registry_key and "end" in nw.node.ports:
            nw.node.ports["end"].set_value(_LOOP_END)
    graph.force_validation()
    return graph


def _busiest_flow(graph: BaseGraph) -> Flow:
    """Assemble and return the flow with the most node executions (the loop)."""
    flows = FlowAssemblyManager().assemble_graph(graph)
    assert flows, "no flows assembled"
    probe = HaywireVM()
    return max(flows, key=lambda f: _run_once(probe, f))


def _run_once(vm: HaywireVM, flow: Flow) -> int:
    trigger = Trigger(source_key=flow.get_subscription_key(), payload={}, timestamp=time.time())
    return vm.execute_control_flow(flow, trigger)


def _make_vm(with_fallback: bool, counts: dict | None = None) -> HaywireVM:
    """A VM whose control-payload fallback is driven entirely from here.

    The source-level call is neutralised; when ``with_fallback`` is True the real
    helper is invoked from a wrapper around ``_execute_control_node`` for every
    fired outlet. ``counts`` (optional) tallies firings and propagating firings.
    """
    vm = HaywireVM()
    vm._fallback_control_payload = lambda *a, **k: None  # type: ignore[method-assign]
    orig = vm._execute_control_node

    def wrapped(node_info, flow, exec_ctx):  # type: ignore[no-untyped-def]
        inlet = exec_ctx.control_pin
        outlet = orig(node_info, flow, exec_ctx)
        if outlet:
            if counts is not None:
                counts["firings"] += 1
                if inlet:  # entered through a real inlet → fallback forwards a payload
                    counts["propagating"] += 1
            if with_fallback:
                _REAL_FALLBACK(vm, node_info.node, inlet, outlet)
        return outlet

    vm._execute_control_node = wrapped  # type: ignore[method-assign]
    return vm


def _bench(vm: HaywireVM, flow: Flow) -> tuple[float, int]:
    """Median nanoseconds per flow run, plus node count."""
    for _ in range(_WARMUP):
        _run_once(vm, flow)
    samples: list[float] = []
    node_count = 0
    for _ in range(_REPEATS):
        t0 = time.perf_counter_ns()
        node_count = _run_once(vm, flow)
        samples.append(float(time.perf_counter_ns() - t0))
    return statistics.median(samples), node_count


def test_control_payload_perf_baseline(library_system):
    """Reproduce the app's loop benchmark and report the undiluted fallback cost."""
    graph = _load_loop_graph()
    flow = _busiest_flow(graph)

    # Firing counts (one instrumented run, fallback off so timing is irrelevant).
    counts = {"firings": 0, "propagating": 0}
    _run_once(_make_vm(False, counts), flow)
    firings = counts["firings"]
    propagating = counts["propagating"]

    on_total, node_count = _bench(_make_vm(True), flow)
    off_total, _ = _bench(_make_vm(False), flow)
    delta = on_total - off_total

    print(
        "\n"
        f"--- control-payload baseline ({_GRAPH}, end={_LOOP_END}, median of {_REPEATS}) ---\n"
        f"  nodes/run            : {node_count}\n"
        f"  control firings/run  : {firings}  ({100 * firings / node_count:.0f}% of nodes)\n"
        f"  propagating edges/run: {propagating}  ({100 * propagating / node_count:.0f}% of nodes)\n"
        f"  ----------------------------------------------------------------\n"
        f"  per-node, fallback ON  : {on_total / node_count:8.1f} ns   <- matches the app's avg\n"
        f"  per-node, fallback OFF : {off_total / node_count:8.1f} ns   <- baseline for the rest\n"
        f"                                          of the EXEC-edge machinery\n"
        f"  fallback cost, viewed at three granularities (same Δ, de-diluted):\n"
        f"    per node             : {delta / node_count:7.1f} ns   <- diluted; what the app avg shows\n"
        f"    per control firing   : {delta / firings:7.1f} ns\n"
        f"    per propagating edge : {delta / propagating:7.1f} ns   <- undiluted; optimise against this\n"
        f"  (informational baseline — not a CI gate; compare across changes)\n"
    )

    # Soft sanity only — this is a baseline to compare against, not a gate.
    assert node_count > 100, "loop did not iterate; check the ForLoop bound"
    assert 0 < propagating <= firings <= node_count
    assert on_total > 0 and off_total > 0
