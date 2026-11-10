# Cross-cut: Dual-Flow Execution Model

> Haywire's defining concept: every graph has two independent flows. **Control pins** define execution order, **data pins** pass values.

## Overview

Inspired by Unreal Engine Blueprints, a Haywire graph is a network of nodes whose ports are typed and split by flow:

- **Control flow (EXEC pins)**: fired in sequence by the VM; determines *when* a node runs. Audio flows use `EXEC_AUDIO` (only audio flows accept it).
- **Data flow (typed pins)**: values pulled lazily when a downstream control fires.

Data evaluation is decoupled from execution sequencing. Assembly compiles a graph into VM instructions and data fetch plans. The interpreter walks control flow, and data is fetched on demand through the edge wrapper. Pin *direction* is `PortType` (`INLET`, `OUTLET`, `SWINGLET`, `CONFIG`); the flow kind is carried by the port's type.

## Modules Involved

| Module | Role | Manifest |
|--------|------|----------|
| haywire-core-engine | Port types, nodes, edges, assembly, VM, interpreter | [→ modules/haywire-core-engine.md](../modules/haywire-core-engine.md) |
| haywire-core-ui | Renders pins and canvas connection rules | [→ modules/haywire-core-ui.md](../modules/haywire-core-ui.md) |
| haybale-core | Concrete nodes and EXEC/GROUP types | [→ modules/haybale-core.md](../modules/haybale-core.md) |
| haybale-audio | `EXEC_AUDIO` and audio event nodes | [→ modules/haybale-audio.md](../modules/haybale-audio.md) |

## Flow

```
Graph (nodes + edges)
     │
     ▼
Assembly  (ControlFlowBuilder + DataFlowBuilder, driven by FlowAssemblyManager)
     │       — emits VM instructions and data fetch plans
     ▼
HaywireVM (execution/vm.py) + Interpreter (execution/interpreter.py)
     │       — walks control flow; pulls data via edge wrappers when needed
     │       — execution groups (execution/execution_group.py) order concurrent flows
     ▼
Node behaviors fire   (node/behavior.py + node/node_wrapper.py)
     │
     ▼
Signal bus (core/signals/bus.py) → UI updates
```

## Key Files

- `packages/haywire-core/src/haywire/core/types/enums.py`: `PortType`, `PortOrigin`, `Propagation`.
- `packages/haywire-core/src/haywire/core/assembly/control_flow_builder.py`: compiles control edges.
- `packages/haywire-core/src/haywire/core/assembly/data_flow_builder.py`: compiles data edges.
- `packages/haywire-core/src/haywire/core/assembly/flow_assembly_manager.py`: drives both builders.
- `packages/haywire-core/src/haywire/core/execution/vm.py`: `HaywireVM`.
- `packages/haywire-core/src/haywire/core/execution/interpreter.py`: `Interpreter`.
- `packages/haywire-core/src/haywire/core/edge/edge_wrapper.py`: lazy data fetch wrapper.
- `barn/haybale-core/haybale_core/types/specs.py`: EXEC type.
- `barn/haybale-audio/haybale_audio/types/exec_audio.py`: `EXEC_AUDIO`.

## Gotchas

- Data edges are lazy: a data node may not run on every control tick. Do not rely on its side effects.
- After modifying nodes or edges in tests, call `force_immediate_validation()` when the `ValidationResult` is needed synchronously (ADR 0002).
- Resume-without-coords on the canvas depends on the `lastMousePos` workaround in `packages/haywire-core/src/haywire/ui/components/graph/canvas.vue`.
- Node skins that draw control vs data pins live in [haybale-graph-editor](../modules/haybale-graph-editor.md) (`skins/node_skin.py`) and [haybale-core](../modules/haybale-core.md) (`skins/widget_node_skin.py`).
