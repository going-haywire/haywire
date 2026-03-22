# Cross-cut: Dual-Flow Model

## Overview

Haywire uses two orthogonal kinds of ports on every node:

- **CONTROL ports** (`FlowType.CONTROL`) — define execution *order*. Think of them as the
  "when does this node run" wire.
- **DATA ports** (`FlowType.DATA`) — pass *values*. Think of them as the "what data does
  this node receive/produce" wire.
- **CALLBACK ports** — freely configurable; used for event-style signalling.

---

## Port Rules (hardcoded in `DataPort.__post_init__`)

| Port type | Direction | `allow_multiple` |
|-----------|-----------|-----------------|
| DATA outlet | out | `True` (fan-out) |
| DATA inlet | in | `False` (single source) |
| EXEC outlet | out | `False` (single target) |
| EXEC inlet | in | `True` (many sources) |
| Pooled inlet | in | `True` (override by PooledType) |

Never set `allow_multiple` manually for DATA/EXEC ports. CALLBACK ports have no hardcoded rules.

---

## Node Types

Node type is determined by control port configuration (see `node/behavior.py`):

| NodeBehavior | Has EXEC in | Has EXEC out | Description |
|---|---|---|---|
| `DATA` | No | No | Pure data transformer; runs when data is demanded |
| `CONTROL` | Yes | Yes | Sequenced node; runs in execution order |
| `EVENT` | No | Yes | Fires execution chain (timer, callback source) |
| `OUTPUT` | Yes | No | Terminal node; receives execution, no output |
| `LOOPBACK` | Yes | Yes (special) | Loop node; uses loopback-stack in VM |

---

## Data Transport: Pipes

Each connected DATA port pair owns a **Pipe**:

- **Eager push** (`is_lazy=False`): When upstream writes a value, pipe pushes it
  downstream immediately and calls `on_change`.
- **Lazy** (`is_lazy=True`): Pipe marks itself dirty but does NOT push. Downstream
  calls `pull_lazy()` at execution time to get the latest value (always-latest semantics).

`is_lazy` is a per-edge flag on `Edge`/`EdgeWrapper`, not per-port.

`resolve_dirty_data()` — called at execution time — pulls all lazy pipes for the node's
inlets, then fires the deferred `on_change` once.

---

## Execution Pipeline

```
Graph (visual/descriptive)
  ↓ FlowAssemblyManager.assemble()
LocalizedDataFlow (per control node — data dependency DAG, topologically sorted)
  ↓ VM.run()
Two-stack VM: done-stack (prevents re-execution) + loopback-stack (loops/sequences)
  ↓ _execute() per node
resolves dirty ports → calls worker(context, **inlet_values)
```

**Key insight**: Data flow is NOT global. Each control node gets its own data dependency DAG
backpropagated from its inlets. Only the data nodes that feed the currently executing control
node are assembled into that node's LocalizedDataFlow.

---

## Lazy Bitmasks (Assembly)

During assembly, a **EVAL_MASK** is created per inlet. At execution time, a **LAZY_MASK** is
created per control node. `EVAL_MASK AND LAZY_MASK` determines which data nodes actually run
for that execution step. If the lazy state changes at runtime (e.g. an edge gains/loses the
lazy flag), the VM triggers reassembly.

---

## Related Source Files

- Port rules: `packages/haywire-core/src/haywire/core/types/port.py` — `DataPort.__post_init__`
- Node behavior: `packages/haywire-core/src/haywire/core/node/behavior.py`
- Pipe transport: `packages/haywire-core/src/haywire/core/types/pipe.py`
- Assembly: `packages/haywire-core/src/haywire/core/assembly/flow_assembly_manager.py`
- VM: `packages/haywire-core/src/haywire/core/execution/vm.py`
