# Cross-cut: Dual-Flow Execution Model

> Haywire's defining concept: every graph has two independent flows — **control pins** define execution order, **data pins** pass values.

## Overview

Inspired by Unreal Engine Blueprints, a Haywire graph is a network of nodes whose ports are typed and split by *flow*:

- **Control flow (white/execution pins)** — fired in sequence by the VM; determines *when* a node runs.
- **Data flow (typed pins)** — passes values lazily; pulled when a downstream control fires.

This split means data evaluation is decoupled from execution sequencing: a data pin is only evaluated on demand, while control pins drive a sequential program. The Assembly stage compiles a Graph into a VM program that the Interpreter walks; data is fetched through the lazy edge wrapper on demand.

## Modules Involved

| Module | Role | Manifest |
|--------|------|----------|
| haywire-core-engine | Defines FlowType, nodes, edges, assembly, VM | [→ modules/haywire-core-engine.md](../modules/haywire-core-engine.md) |
| haywire-core-ui | Renders control vs data pins; canvas connection rules | [→ modules/haywire-core-ui.md](../modules/haywire-core-ui.md) |
| haybale-core | Concrete nodes that use both flows | [→ modules/haybale-core.md](../modules/haybale-core.md) |

## Flow

```
Graph (nodes + edges)
     │
     ▼
Assembly  (control_flow_builder + data_flow_builder + flow_assembly_manager)
     │       — emits VM instructions and data fetch plans
     ▼
Interpreter / VM  (execution/interpreter.py + execution/vm.py)
     │       — walks control flow; pulls data via edge wrappers when needed
     ▼
Node behaviors fire   (node/behavior.py + node/node_wrapper.py)
     │       — emit signals on completion / state change
     ▼
Signal bus  (core/session/signals/bus.py) → UI updates
```

## Key Files

- `packages/haywire-core/src/haywire/core/types/` — `FlowType` enum and port types.
- `packages/haywire-core/src/haywire/core/assembly/control_flow_builder.py` — compiles control edges.
- `packages/haywire-core/src/haywire/core/assembly/data_flow_builder.py` — compiles data edges.
- `packages/haywire-core/src/haywire/core/assembly/flow_assembly_manager.py` — drives both builders.
- `packages/haywire-core/src/haywire/core/execution/vm.py` — control-flow VM.
- `packages/haywire-core/src/haywire/core/execution/interpreter.py` — instruction interpreter.
- `packages/haywire-core/src/haywire/core/edge/edge_wrapper.py` — lazy data fetch wrapper.

## Gotchas

- `pin.flow_type.value` returns `'data'` / `'control'`; `str(pin.flow_type)` returns `'FlowType.DATA'`. Canvas connection logic depends on the string form — be deliberate (see `.insights/project_graph_canvas_connection.md`).
- Data edges are lazy: a data node may not run on every control tick. Be careful when relying on side effects from data nodes.
- After modifying nodes/edges in tests, call `force_immediate_validation()` to flush the dirty queue.
- Resume-without-coords on the canvas relies on a `lastMousePos` workaround in `components/graph/canvas.vue`.
