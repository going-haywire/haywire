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
    from haybale_core.nodes.logger import LoggerNode
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
        "Print": LoggerNode,
        "Shutdown": ShutdownNode,
    }

    graph = BaseGraph(filestem="bench loop")
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

    graph = BaseGraph(filestem="bench bare")
    nw = graph.create_node_wrapper(BenchBareNode.class_identity.registry_key, position=(0, 0))
    graph.force_validation()

    node = nw.node
    ctx = ExecutionContext(global_ctx={}, local_ctx={})
    inner = 2000

    def run() -> None:
        for _ in range(inner):
            node._execute(ctx)

    return Prepared(run=run, ops=inner, repeats=15, warmup=5)


# ---------------------------------------------------------------------------
# failure-path cases (S2, failure poisoning)
#
# One control node (BenchSinkNode) whose localized data flow is a 32-node chain of
# BenchDataPassNode plus a fan-in joining node 16 and node 32. The root's own inlet
# is set every run so the whole chain is dirty and evaluates each frame.
# ---------------------------------------------------------------------------
_CHAIN_LENGTH = 32
_HALF_LOOP_END = 500


def _fire_only_flow(graph):
    """Assemble ``graph``; return a callable firing its busiest flow and that flow's exec count."""
    from haywire.core.assembly.flow_assembly_manager import FlowAssemblyManager
    from haywire.core.execution.event_source import Trigger
    from haywire.core.execution.vm import HaywireVM

    graph.force_validation()
    flows = FlowAssemblyManager().assemble_graph(graph)
    vm = HaywireVM()

    def fire_one(flow) -> int:
        trig = Trigger(source_key=flow.get_subscription_key(), payload={}, timestamp=0.0)
        return vm.execute_control_flow(flow, trig)

    flow = max(flows, key=fire_one)
    return (lambda: fire_one(flow)), fire_one(flow)


def _build_chain_graph(root_raises: bool):
    from haybale_core.nodes.events.begin_play import BeginPlayNode
    from haybale_testing.nodes.benchmark.bench_data_pass_node import BenchDataPassNode
    from haybale_testing.nodes.benchmark.bench_data_raise_node import BenchDataRaiseNode
    from haybale_testing.nodes.benchmark.bench_fan_in_node import BenchFanInNode
    from haybale_testing.nodes.benchmark.bench_sink_node import BenchSinkNode

    from haywire.core.graph.base import BaseGraph

    graph = BaseGraph(filestem="bench chain")

    def make(cls) -> str:
        nw = graph.create_node_wrapper(cls.class_identity.registry_key, position=(0, 0))
        assert nw is not None, f"failed to create benchmark node {cls.__name__}"
        return nw.node_id

    begin, sink, fan_in = make(BeginPlayNode), make(BenchSinkNode), make(BenchFanInNode)
    chain = [
        make(BenchDataRaiseNode if (root_raises and i == 0) else BenchDataPassNode)
        for i in range(_CHAIN_LENGTH)
    ]
    graph.create_edge_wrapper(begin, "exec", sink, "exec_in")
    for upstream, downstream in zip(chain, chain[1:], strict=False):
        graph.create_edge_wrapper(upstream, "y", downstream, "x")
    graph.create_edge_wrapper(chain[_CHAIN_LENGTH // 2 - 1], "y", fan_in, "a")
    graph.create_edge_wrapper(chain[-1], "y", fan_in, "b")
    graph.create_edge_wrapper(fan_in, "y", sink, "x")
    return graph, graph.get_node_wrapper(chain[0]).node


def _prepare_chain(root_raises: bool) -> Prepared:
    graph, root = _build_chain_graph(root_raises)
    fire, node_count = _fire_only_flow(graph)
    counter = {"i": 0}

    def run() -> None:
        counter["i"] += 1
        root.ports["x"].set_value(float(counter["i"]))
        fire()

    return Prepared(run=run, ops=max(node_count, _CHAIN_LENGTH + 2), repeats=15, warmup=5)


def _prepare_graph_data_chain_ok() -> Prepared:
    return _prepare_chain(root_raises=False)


def _prepare_graph_data_chain_root_fails() -> Prepared:
    return _prepare_chain(root_raises=True)


def _prepare_graph_loop_half_failing() -> Prepared:
    from haybale_core.nodes.events.begin_play import BeginPlayNode
    from haybale_core.nodes.for_loop import ForLoopNode
    from haybale_testing.nodes.benchmark.bench_loop_raise_node import BenchLoopRaiseNode
    from haybale_testing.nodes.benchmark.bench_sink_node import BenchSinkNode

    from haywire.core.graph.base import BaseGraph

    graph = BaseGraph(filestem="bench loop half failing")
    ids = {}
    for short, cls in {
        "begin": BeginPlayNode,
        "loop": ForLoopNode,
        "raise": BenchLoopRaiseNode,
        "sink": BenchSinkNode,
    }.items():
        nw = graph.create_node_wrapper(cls.class_identity.registry_key, position=(0, 0))
        assert nw is not None, f"failed to create benchmark node {cls.__name__}"
        ids[short] = nw.node_id
    graph.create_edge_wrapper(ids["begin"], "exec", ids["loop"], "execute")
    graph.create_edge_wrapper(ids["loop"], "loop_body", ids["sink"], "exec_in")
    graph.create_edge_wrapper(ids["loop"], "index", ids["raise"], "x")
    graph.create_edge_wrapper(ids["raise"], "y", ids["sink"], "x")
    graph.get_node_wrapper(ids["loop"]).node.ports["end"].set_value(_HALF_LOOP_END)
    fire, _node_count = _fire_only_flow(graph)
    # Fixed per-iteration count (loop node, data node, sink) plus BeginPlay and the loop's exit:
    # a blocked sink does not execute, so counting executions would shrink the denominator.
    return Prepared(run=fire, ops=3 * _HALF_LOOP_END + 2, repeats=15, warmup=5)


def _prepare_node_execute_raises() -> Prepared:
    from haybale_testing.nodes.benchmark.bench_data_raise_node import BenchDataRaiseNode, BenchFailure

    from haywire.core.execution.execution_context import ExecutionContext
    from haywire.core.graph.base import BaseGraph

    graph = BaseGraph(filestem="bench raises")
    nw = graph.create_node_wrapper(BenchDataRaiseNode.class_identity.registry_key, position=(0, 0))
    assert nw is not None, "failed to create BenchDataRaiseNode"
    graph.force_validation()
    node = nw.node
    port = node.ports["x"]
    ctx = ExecutionContext(global_ctx={}, local_ctx={})
    inner = 2000

    def run() -> None:
        for i in range(inner):
            port.set_value(float(i))  # dirty the inlet so every call reaches the worker
            try:
                node._execute(ctx)
            except BenchFailure:
                pass

    return Prepared(run=run, ops=inner, repeats=15, warmup=5)


# ---------------------------------------------------------------------------
# micro cases: ImageValue storage conversions (haybale-image)
#
# Each run() wraps a fresh value so the per-value cache never hides the
# conversion. Inputs come from a fixed-seed generator. GPU cases synchronize
# before returning so the timing covers the device work.
# ---------------------------------------------------------------------------
_IMG_REPEATS = 30
_SR_MODEL_ENV = "HAYWIRE_BENCH_SR_MODEL"
_SR_MODEL_SHA256 = "27985aa2198711ecd72f9bb274ec7b164e018fc9ce2933daaa7c7ab36a2bd3fe"


def _bgr_frame(height: int, width: int):
    import numpy as np

    return np.random.default_rng(0).integers(0, 256, (height, width, 3), dtype=np.uint8)


def _gpu_device() -> Optional[str]:
    """``"cuda"`` or ``"mps"`` when torch and that device are available, else ``None``."""
    try:
        import torch
    except ImportError:
        return None
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return None


def _sync(device: str) -> None:
    import torch

    if device == "cuda":
        torch.cuda.synchronize()
    else:
        torch.mps.synchronize()


def _prepare_img_wrap_1080p() -> Prepared:
    from haybale_image.value import ChannelOrder, ImageValue

    frame = _bgr_frame(1080, 1920)

    def run() -> None:
        ImageValue.from_array(frame, order=ChannelOrder.BGR)

    return Prepared(run=run, ops=1, repeats=_IMG_REPEATS, warmup=5)


def _prepare_img_cpu_f32_1080p() -> Prepared:
    import numpy as np

    from haybale_image.value import ChannelOrder, ImageValue

    frame = _bgr_frame(1080, 1920)

    def run() -> None:
        ImageValue.from_array(frame, order=ChannelOrder.BGR).array(np.float32, ChannelOrder.RGB)

    return Prepared(run=run, ops=1, repeats=_IMG_REPEATS, warmup=5)


def _prepare_img_gpu_up_f16_1080p() -> Prepared:
    import torch

    from haybale_image.value import ChannelOrder, ImageValue

    dev = _gpu_device()
    assert dev is not None
    frame = _bgr_frame(1080, 1920)

    def run() -> None:
        ImageValue.from_array(frame, order=ChannelOrder.BGR).tensor(dev, torch.float16)
        _sync(dev)

    return Prepared(run=run, ops=1, repeats=_IMG_REPEATS, warmup=5)


def _prepare_img_gpu_down_u8_1080p() -> Prepared:
    import numpy as np
    import torch

    from haybale_image.value import ChannelOrder, ImageValue

    dev = _gpu_device()
    assert dev is not None
    t_f16 = ImageValue.from_array(_bgr_frame(1080, 1920)).tensor(dev, torch.float16)
    _sync(dev)

    def run() -> None:
        ImageValue.from_tensor(t_f16).array(np.uint8, ChannelOrder.BGR)

    return Prepared(run=run, ops=1, repeats=_IMG_REPEATS, warmup=5)


def _prepare_img_gpu_trip_1080p() -> Prepared:
    import numpy as np
    import torch

    from haybale_image.value import ChannelOrder, ImageValue

    dev = _gpu_device()
    assert dev is not None
    frame = _bgr_frame(1080, 1920)

    def run() -> None:
        t = ImageValue.from_array(frame, order=ChannelOrder.BGR).tensor(dev, torch.float16)
        ImageValue.from_tensor(t).array(np.uint8, ChannelOrder.BGR)

    return Prepared(run=run, ops=1, repeats=_IMG_REPEATS, warmup=5)


def _sr_model_path() -> Optional[str]:
    """Return ``$HAYWIRE_BENCH_SR_MODEL``, or ``None`` if unset, missing, or spandrel absent."""
    import importlib.util
    import os

    path = os.environ.get(_SR_MODEL_ENV)
    if not path or not os.path.isfile(path) or importlib.util.find_spec("spandrel") is None:
        return None
    return path


def _prepare_img_sr2x_540p() -> Prepared:
    import hashlib

    import numpy as np
    import torch
    from spandrel import ModelLoader

    from haybale_image.value import ChannelOrder, ImageValue

    dev = _gpu_device()
    path = _sr_model_path()
    assert dev is not None and path is not None
    with open(path, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    if digest != _SR_MODEL_SHA256:
        raise ValueError(f"{path} has sha256 {digest}, expected {_SR_MODEL_SHA256}")
    model = ModelLoader().load_from_file(path).to(dev).eval()
    dtype = torch.float32
    if model.supports_half:
        model = model.half()
        dtype = torch.float16
    frame = _bgr_frame(540, 960)

    def run() -> None:
        t = ImageValue.from_array(frame, order=ChannelOrder.BGR).tensor(dev, dtype)
        with torch.inference_mode():
            out = model(t)
        ImageValue.from_tensor(out).array(np.uint8, ChannelOrder.BGR)

    return Prepared(run=run, ops=1, repeats=_IMG_REPEATS, warmup=5)


def _image_cases() -> List[Case]:
    """The ``img_*`` cases this environment can run: GPU cases need torch + CUDA/MPS, SR also a model."""
    cases = [
        Case("img_wrap_1080p", "micro", "ns", _prepare_img_wrap_1080p),
        Case("img_cpu_f32_1080p", "micro", "ns", _prepare_img_cpu_f32_1080p),
    ]
    if _gpu_device() is None:
        return cases
    cases += [
        Case("img_gpu_up_f16_1080p", "micro", "ns", _prepare_img_gpu_up_f16_1080p),
        Case("img_gpu_down_u8_1080p", "micro", "ns", _prepare_img_gpu_down_u8_1080p),
        Case("img_gpu_trip_1080p", "micro", "ns", _prepare_img_gpu_trip_1080p),
    ]
    if _sr_model_path() is not None:
        cases.append(Case("img_sr2x_540p", "micro", "ns", _prepare_img_sr2x_540p))
    return cases


CASES: List[Case] = [
    Case("graph_loop", "graph", "ns", _prepare_graph_loop),
    Case("node_execute_bare", "micro", "ns", _prepare_node_execute_bare),
    Case("graph_data_chain_ok", "graph", "ns", _prepare_graph_data_chain_ok),
    Case("graph_data_chain_root_fails", "graph", "ns", _prepare_graph_data_chain_root_fails),
    Case("graph_loop_half_failing", "graph", "ns", _prepare_graph_loop_half_failing),
    Case("node_execute_raises", "micro", "ns", _prepare_node_execute_raises),
    *_image_cases(),
]


def get_cases(only: Optional[str] = None) -> List[Case]:
    """All cases, or those whose name contains ``only`` (case-name filter)."""
    if only is None:
        return list(CASES)
    return [c for c in CASES if only in c.name]
